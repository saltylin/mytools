package main

import (
	"bufio"
	"context"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"
)

type Job struct {
	ID   string
	Cmd  string
	Args []string
	Env  map[string]string
	Cwd  string
}

type JobResult struct {
	JobID     string
	ExitCode  int
	Err       error
	StartedAt time.Time
	EndedAt   time.Time
}

func main() {
	var (
		inputFile    string
		binPath      string
		sharedArgs   []string
		maxParallel  int
		stopOnError  bool
		workingDir   string
		printVersion bool
	)

	flag.StringVar(&inputFile, "f", "", "Text file with one argument per line. Use '-' for stdin.")
	flag.StringVar(&binPath, "b", "", "Executable path to run for each job.")
	flag.IntVar(&maxParallel, "p", 4, "Maximum jobs to run concurrently.")
	flag.BoolVar(&stopOnError, "x", false, "Cancel remaining jobs after the first failure.")
	flag.StringVar(&workingDir, "C", "", "Change directory before running any jobs.")
	flag.BoolVar(&printVersion, "V", false, "Print version and exit.")
	flag.Func("a", "Shared argument appended to every job (repeatable).", func(value string) error {
		if value == "" {
			return nil
		}
		sharedArgs = append(sharedArgs, value)
		return nil
	})
	flag.Parse()

	if printVersion {
		fmt.Println("mytools runjobs v0.1.0")
		return
	}

	if binPath == "" {
		fmt.Fprintln(os.Stderr, "error: -b is required (path to executable to run)")
		os.Exit(2)
	}
	if inputFile == "" {
		fmt.Fprintln(os.Stderr, "error: -f is required (use a text file or '-')")
		os.Exit(2)
	}

	if workingDir != "" {
		if err := os.Chdir(workingDir); err != nil {
			fmt.Fprintf(os.Stderr, "error: chdir %q: %v\n", workingDir, err)
			os.Exit(2)
		}
	}

	jobs, err := loadJobsFromInput(binPath, sharedArgs, inputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: load jobs: %v\n", err)
		os.Exit(2)
	}

	if len(jobs) == 0 {
		fmt.Fprintln(os.Stderr, "error: no jobs found")
		os.Exit(2)
	}

	if maxParallel <= 0 {
		maxParallel = 1
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Handle signals to cancel context
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		s := <-sigCh
		fmt.Fprintf(os.Stderr, "\nreceived signal %s, cancelling...\n", s)
		cancel()
	}()

	successCount, failCount := runJobs(ctx, jobs, maxParallel, stopOnError)

	fmt.Printf("jobs total=%d success=%d failed=%d\n", len(jobs), successCount, failCount)

	if failCount > 0 {
		os.Exit(1)
	}
}

func loadJobsFromInput(binPath string, sharedArgs []string, path string) ([]Job, error) {
	var r io.Reader
	if path == "-" {
		r = os.Stdin
	} else {
		f, err := os.Open(filepath.Clean(path))
		if err != nil {
			return nil, err
		}
		defer func() { _ = f.Close() }()
		r = f
	}
	sc := bufio.NewScanner(r)
	buf := make([]byte, 0, 64*1024)
	sc.Buffer(buf, 10*1024*1024)
	var jobs []Job
	for sc.Scan() {
		arg := sc.Text()
		arg = strings.TrimSpace(arg)
		if arg == "" {
			continue
		}
		fields := strings.Fields(arg)
		if len(fields) == 0 {
			continue
		}
		jobArgs := make([]string, 0, len(sharedArgs)+len(fields))
		jobArgs = append(jobArgs, sharedArgs...)
		jobArgs = append(jobArgs, fields...)
		jobs = append(jobs, Job{
			ID:   fmt.Sprintf("%s-%d", filepath.Base(binPath), len(jobs)+1),
			Cmd:  binPath,
			Args: jobArgs,
		})
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	return jobs, nil
}

func runJobs(ctx context.Context, jobs []Job, maxParallel int, stopOnError bool) (int, int) {
	sema := make(chan struct{}, maxParallel)
	var (
		wg       sync.WaitGroup
		results  = make([]JobResult, len(jobs))
		onceFail sync.Once
		cancelFn context.CancelFunc
	)
	ctx, cancelFn = context.WithCancel(ctx)
	defer cancelFn()

	for i := range jobs {
		wg.Add(1)
		i := i
		go func() {
			defer wg.Done()
			select {
			case sema <- struct{}{}:
				// acquired
				defer func() { <-sema }()
			case <-ctx.Done():
				results[i] = JobResult{
					JobID:    jobs[i].ID,
					ExitCode: 1,
					Err:      ctx.Err(),
				}
				return
			}

			start := time.Now()
			exitCode, err := runOne(ctx, jobs[i])
			end := time.Now()
			results[i] = JobResult{
				JobID:     jobs[i].ID,
				ExitCode:  exitCode,
				Err:       err,
				StartedAt: start,
				EndedAt:   end,
			}

			if stopOnError && (err != nil || exitCode != 0) {
				onceFail.Do(func() { cancelFn() })
			}
		}()
	}

	wg.Wait()
	var (
		successCount int
		failCount    int
	)
	for _, r := range results {
		if r.ExitCode == 0 && r.Err == nil {
			successCount++
		} else {
			failCount++
		}
	}
	return successCount, failCount
}

func runOne(ctx context.Context, job Job) (int, error) {
	if job.Cmd == "" {
		return 1, errors.New("empty command")
	}
	cmd := exec.CommandContext(ctx, job.Cmd, job.Args...)
	if job.Cwd != "" {
		cmd.Dir = job.Cwd
	}
	// Inherit base environment, then overlay job.Env
	cmd.Env = os.Environ()
	if len(job.Env) > 0 {
		for k, v := range job.Env {
			cmd.Env = append(cmd.Env, fmt.Sprintf("%s=%s", k, v))
		}
	}

	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return 1, err
	}
	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		return 1, err
	}

	if err := cmd.Start(); err != nil {
		return 1, err
	}

	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		_, _ = io.Copy(os.Stdout, stdoutPipe)
	}()
	go func() {
		defer wg.Done()
		_, _ = io.Copy(os.Stderr, stderrPipe)
	}()

	waitErr := cmd.Wait()
	wg.Wait()

	// Extract exit code if available
	exitCode := 0
	if waitErr != nil {
		var ee *exec.ExitError
		if errors.As(waitErr, &ee) {
			if status, ok := ee.Sys().(syscall.WaitStatus); ok {
				exitCode = status.ExitStatus()
			} else {
				exitCode = 1
			}
		} else {
			exitCode = 1
		}
	}
	return exitCode, waitErr
}
