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
)

type Job struct {
	ID   string
	Cmd  string
	Args []string
	Env  map[string]string
	Cwd  string
}

type JobSource interface {
	Next(ctx context.Context) (Job, bool, error)
	Close() error
}

type scannerJobSource struct {
	scanner    *bufio.Scanner
	closer     io.Closer
	binPath    string
	sharedArgs []string
	index      int
}

func newJobSource(binPath string, sharedArgs []string, path string) (JobSource, error) {
	var (
		reader io.Reader
		closer io.Closer
	)
	if path == "" {
		reader = os.Stdin
	} else {
		f, err := os.Open(filepath.Clean(path))
		if err != nil {
			return nil, err
		}
		reader = f
		closer = f
	}

	sc := bufio.NewScanner(reader)
	buf := make([]byte, 0, 64*1024)
	sc.Buffer(buf, 10*1024*1024)

	return &scannerJobSource{
		scanner:    sc,
		closer:     closer,
		binPath:    binPath,
		sharedArgs: append([]string(nil), sharedArgs...),
	}, nil
}

func (s *scannerJobSource) Next(ctx context.Context) (Job, bool, error) {
	for {
		if err := ctx.Err(); err != nil {
			return Job{}, false, err
		}
		if !s.scanner.Scan() {
			if err := s.scanner.Err(); err != nil {
				return Job{}, false, err
			}
			return Job{}, false, nil
		}
		line := strings.TrimSpace(s.scanner.Text())
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) == 0 {
			continue
		}
		s.index++
		args := make([]string, 0, len(s.sharedArgs)+len(fields))
		args = append(args, s.sharedArgs...)
		args = append(args, fields...)
		job := Job{
			ID:   fmt.Sprintf("%s-%d", filepath.Base(s.binPath), s.index),
			Cmd:  s.binPath,
			Args: args,
		}
		return job, true, nil
	}
}

func (s *scannerJobSource) Close() error {
	if s.closer != nil {
		return s.closer.Close()
	}
	return nil
}

func main() {
	var (
		inputFile    string
		binPath      string
		maxParallel  int
		stopOnError  bool
		workingDir   string
		printVersion bool
		printCmd     bool
	)

	args := os.Args[1:]
	coreArgs := make([]string, 0, len(args))
	sharedArgs := make([]string, 0)
	var (
		useStdin  bool
		sawShared bool
	)
	for i := 0; i < len(args); {
		token := args[i]
		switch token {
		case "--":
			if useStdin {
				fmt.Fprintln(os.Stderr, "error: '--' may only be provided once")
				os.Exit(2)
			}
			useStdin = true
			if i != len(args)-1 {
				fmt.Fprintln(os.Stderr, "error: '--' must be the final argument")
				os.Exit(2)
			}
			i = len(args)
		case "-a":
			if sawShared {
				fmt.Fprintln(os.Stderr, "error: '-a' may only be provided once")
				os.Exit(2)
			}
			sawShared = true
			i++
			for i < len(args) {
				if args[i] == "--" {
					if useStdin {
						fmt.Fprintln(os.Stderr, "error: '--' may only be provided once")
						os.Exit(2)
					}
					useStdin = true
					if i != len(args)-1 {
						fmt.Fprintln(os.Stderr, "error: '--' must be the final argument")
						os.Exit(2)
					}
					i = len(args)
					break
				}
				if args[i] == "-a" {
					fmt.Fprintln(os.Stderr, "error: '-a' may only be provided once")
					os.Exit(2)
				}
				sharedArgs = append(sharedArgs, args[i])
				i++
			}
		default:
			coreArgs = append(coreArgs, token)
			i++
		}
	}

	fs := flag.NewFlagSet("runjobs", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)
	fs.Usage = func() {
		out := fs.Output()
		fmt.Fprintf(out, "Usage: %s -b path [-f jobs.txt | --] [-p N] [-x] [-C dir] [-e] [-a shared... [--]]\n", os.Args[0])
		fmt.Fprintln(out)
		fmt.Fprintln(out, "Options:")
		fs.PrintDefaults()
		fmt.Fprintln(out, "  -a shared...      append shared arguments to every job; must be last option")
		fmt.Fprintln(out, "  --                optional sentinel that must be last argument; read jobs from stdin")
	}
	fs.StringVar(&inputFile, "f", "", "Text file with one job per line (default: stdin).")
	fs.StringVar(&binPath, "b", "", "Executable path to run for each job.")
	fs.IntVar(&maxParallel, "p", 4, "Maximum jobs to run concurrently.")
	fs.BoolVar(&stopOnError, "x", false, "Cancel remaining jobs after the first failure.")
	fs.StringVar(&workingDir, "C", "", "Change directory before running any jobs.")
	fs.BoolVar(&printVersion, "V", false, "Print version and exit.")
	fs.BoolVar(&printCmd, "e", false, "Echo each job's command and arguments before execution.")
	if err := fs.Parse(coreArgs); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return
		}
		os.Exit(2)
	}

	if fs.NArg() > 0 {
		fmt.Fprintf(os.Stderr, "error: unexpected positional arguments: %s\n", strings.Join(fs.Args(), " "))
		os.Exit(2)
	}

	if printVersion {
		fmt.Println("mytools runjobs v0.1.0")
		return
	}

	if binPath == "" {
		fmt.Fprintln(os.Stderr, "error: -b is required (path to executable to run)")
		os.Exit(2)
	}

	resolvedBin, err := ensureExecutable(binPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(2)
	}
	binPath = resolvedBin

	if useStdin {
		if inputFile != "" {
			fmt.Fprintln(os.Stderr, "error: cannot combine -f with '--'")
			os.Exit(2)
		}
	} else if inputFile == "" {
		fmt.Fprintln(os.Stderr, "error: provide -f <file> or terminate arguments with '--' to read from stdin")
		os.Exit(2)
	}

	if workingDir != "" {
		if err := os.Chdir(workingDir); err != nil {
			fmt.Fprintf(os.Stderr, "error: chdir %q: %v\n", workingDir, err)
			os.Exit(2)
		}
	}

	jobSrc, err := newJobSource(binPath, sharedArgs, inputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: load jobs: %v\n", err)
		os.Exit(2)
	}
	defer func() { _ = jobSrc.Close() }()

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

	successCount, failCount, totalJobs, runErr := runJobs(ctx, jobSrc, maxParallel, stopOnError, printCmd)
	if runErr != nil && !errors.Is(runErr, context.Canceled) && !errors.Is(runErr, context.DeadlineExceeded) {
		fmt.Fprintf(os.Stderr, "error: %v\n", runErr)
		os.Exit(2)
	}

	fmt.Printf("jobs total=%d success=%d failed=%d\n", totalJobs, successCount, failCount)

	if failCount > 0 {
		os.Exit(1)
	}
}

func runJobs(ctx context.Context, src JobSource, maxParallel int, stopOnError bool, printCmd bool) (int, int, int, error) {
	sema := make(chan struct{}, maxParallel)
	var (
		wg           sync.WaitGroup
		onceFail     sync.Once
		cancelFn     context.CancelFunc
		startMu      sync.Mutex
		startCond    = sync.NewCond(&startMu)
		nextToStart  int
		countMu      sync.Mutex
		progressMu   sync.Mutex
		successCount int
		failCount    int
		totalJobs    int
		finishedJobs int
	)
	ctx, cancelFn = context.WithCancel(ctx)
	defer cancelFn()

	// Setup progress bar if TTY
	showProgress := isTerminal(os.Stdout)
	if showProgress {
		// Save cursor position
		fmt.Print("\033[s")
	}

	updateProgress := func() {
		if !showProgress {
			return
		}
		progressMu.Lock()
		defer progressMu.Unlock()
		countMu.Lock()
		finished := finishedJobs
		total := totalJobs
		success := successCount
		failed := failCount
		countMu.Unlock()
		// Save current position, move to bottom, print progress, restore position
		fmt.Print("\033[s")      // Save cursor
		fmt.Print("\033[999;1H") // Move to row 999, col 1 (bottom)
		fmt.Print("\033[K")      // Clear line
		if total > 0 {
			fmt.Print("\033[32m") // Green color
			fmt.Printf("[%d/%d] jobs completed (success: %d, failed: %d)", finished, total, success, failed)
			fmt.Print("\033[0m") // Reset color
		}
		fmt.Print("\033[u") // Restore cursor
	}

	var iterationErr error

	for {
		job, ok, err := src.Next(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
				break
			}
			iterationErr = err
			break
		}
		if !ok {
			break
		}
		idx := totalJobs
		countMu.Lock()
		totalJobs++
		countMu.Unlock()
		updateProgress()

		wg.Add(1)
		go func(job Job, idx int) {
			defer wg.Done()

			releaseOnce := func() {
				startMu.Lock()
				if nextToStart == idx {
					nextToStart++
					startCond.Broadcast()
				}
				startMu.Unlock()
			}
			released := false
			release := func() {
				if !released {
					released = true
					releaseOnce()
				}
			}
			defer release()

			select {
			case sema <- struct{}{}:
				defer func() { <-sema }()
			case <-ctx.Done():
				countMu.Lock()
				failCount++
				finishedJobs++
				countMu.Unlock()
				updateProgress()
				return
			}

			startMu.Lock()
			for idx != nextToStart {
				startCond.Wait()
			}
			startMu.Unlock()

			exitCode, err := runOne(ctx, job, printCmd, release)
			countMu.Lock()
			finishedJobs++
			if err != nil || exitCode != 0 {
				failCount++
			} else {
				successCount++
			}
			countMu.Unlock()

			updateProgress()

			if (err != nil || exitCode != 0) && stopOnError {
				onceFail.Do(func() { cancelFn() })
			}
		}(job, idx)
	}

	wg.Wait()

	// Clear progress bar
	if showProgress {
		fmt.Print("\033[999;1H\033[K") // Move to bottom and clear
		fmt.Print("\033[u")            // Restore original cursor position
	}

	return successCount, failCount, totalJobs, iterationErr
}

func isTerminal(f *os.File) bool {
	stat, err := f.Stat()
	if err != nil {
		return false
	}
	return stat.Mode()&os.ModeCharDevice != 0
}

func runOne(ctx context.Context, job Job, printCmd bool, onStarted func()) (int, error) {
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

	release := func() {
		if onStarted != nil {
			onStarted()
		}
	}
	released := false
	defer func() {
		if !released {
			release()
		}
	}()

	// Check if stdout/stderr are terminals to preserve colors
	stdoutIsTTY := isTerminal(os.Stdout)
	stderrIsTTY := isTerminal(os.Stderr)

	var wg sync.WaitGroup
	if stdoutIsTTY && stderrIsTTY {
		// Direct output to preserve colors
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
	} else {
		// Use pipes when not a TTY (e.g., redirected output)
		stdoutPipe, err := cmd.StdoutPipe()
		if err != nil {
			return 1, err
		}
		stderrPipe, err := cmd.StderrPipe()
		if err != nil {
			return 1, err
		}

		wg.Add(2)
		go func() {
			defer wg.Done()
			_, _ = io.Copy(os.Stdout, stdoutPipe)
		}()
		go func() {
			defer wg.Done()
			_, _ = io.Copy(os.Stderr, stderrPipe)
		}()
	}

	if printCmd {
		fmt.Printf("+ %s\n", formatCommand(job.Cmd, job.Args))
	}

	if err := cmd.Start(); err != nil {
		return 1, err
	}
	release()
	released = true

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

func formatCommand(cmd string, args []string) string {
	parts := make([]string, 0, len(args)+1)
	parts = append(parts, shellQuote(cmd))
	for _, a := range args {
		parts = append(parts, shellQuote(a))
	}
	return strings.Join(parts, " ")
}

func shellQuote(s string) string {
	const specialChars = "\"#$&()*;<>?[\\]^`{|}~"
	if s == "" {
		return "''"
	}
	needs := false
	for _, r := range s {
		if r == '\'' {
			return "'" + strings.ReplaceAll(s, "'", `'"'"'`) + "'"
		}
		if r <= ' ' || strings.ContainsRune(specialChars, r) {
			needs = true
		}
	}
	if needs {
		return "'" + s + "'"
	}
	return s
}

func ensureExecutable(bin string) (string, error) {
	resolved, err := exec.LookPath(bin)
	if err != nil {
		return "", fmt.Errorf("executable %q not found: %w", bin, err)
	}
	info, err := os.Stat(resolved)
	if err != nil {
		return "", fmt.Errorf("stat %q: %w", resolved, err)
	}
	if info.IsDir() {
		return "", fmt.Errorf("executable %q is a directory", resolved)
	}
	if info.Mode()&0111 == 0 {
		return "", fmt.Errorf("executable %q is not marked executable", resolved)
	}
	return resolved, nil
}
