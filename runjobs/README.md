# runjobs

Run many subprocess jobs with a max concurrency limit.

## Install

```
go install github.com/saltylin/mytools/runjobs@latest
```

Or build locally:

```
go build -o runjobs ./runjobs
```

## Usage

```
./runjobs -b /path/to/your_binary [-f jobs.txt | --] [-p 4] [-x] [-C dir] [-e] [-w 600] [-a shared1 shared2 ... [--]]
```

- `-b`: Executable path (for example, a bash script) run for each job. **Required.** The path must resolve to an executable file (or a binary discoverable via `$PATH`); `runjobs` exits immediately if it cannot find or execute it.
- `-f jobs.txt`: Text file where each non-empty line is trimmed and split on whitespace into positional arguments for one job. Mutually exclusive with `--`.
- `--`: Optional sentinel that must be the very last argument; when present, jobs are read from stdin. You can use it alone (no shared args) or after `-a`.
- `-a shared1 shared2 ...`: Must be the final option. Every token after `-a` becomes a shared argument prepended to each job. When you also read jobs from stdin, place `--` after the shared arguments (for example `-a --verbose --flag=123 --`).
- `-p`: Maximum number of jobs to run at the same time (default: 4).
- `-x`: Cancel remaining jobs when any job fails.
- `-C`: Change to this directory before running jobs.
- `-V`: Print version and exit.
- `-e`: Echo each composed command line before execution.
- `-w`: Warning threshold in seconds for long-running jobs. If a job runs longer than this duration, a warning is printed. Warnings repeat every threshold interval (default: 600 seconds).

## Input file format

Provide a plain text file where each non-empty line is trimmed, split on whitespace, and the resulting tokens become positional arguments appended after any `-a` flags. If the file contains 10 lines, 10 jobs are launched.

Example `args.txt`:

```
alpha
beta
foo bar baz
```

Command:

```
./runjobs -b ./scripts/run.sh -f args.txt -p 3 -a --verbose --flag=123
```

This launches:

```
./scripts/run.sh --verbose --flag=123 alpha
./scripts/run.sh --verbose --flag=123 beta
./scripts/run.sh --verbose --flag=123 foo bar baz
```

When reading jobs from stdin:

```
cat args.txt | ./runjobs -b ./scripts/run.sh -a --verbose --flag=123 --
```

Without shared arguments:

```
cat args.txt | ./runjobs -b ./scripts/run.sh --
```

## Output

Stdout and stderr from each process are streamed directly without additional prefixes. Colors from job output are preserved when running in a terminal.

### Progress Bar

When running in a terminal (TTY), a green progress bar appears at the bottom of the screen showing job completion status. The progress bar is automatically disabled when output is redirected to a file or pipe.

```
[5/10] jobs completed (success: 4, failed: 1)
```

The progress bar updates in real-time as jobs finish, showing:
- Number of completed jobs vs total jobs
- Success count
- Failure count

Example output:

```
$ ./runjobs -b ./scripts/run.sh -f jobs.txt -p 3
Job output line 1
Job output line 2
[2/10] jobs completed (success: 2, failed: 0)
More job output...
[5/10] jobs completed (success: 4, failed: 1)
...
jobs total=10 success=9 failed=1
```

The progress bar is automatically cleared when all jobs complete.

### Long-Running Job Warnings

When a job runs longer than the warning threshold (default: 600 seconds), `runjobs` prints a warning message to stderr showing the job command and its running duration. Warnings repeat every threshold interval, so if a job runs for 1 hour with a 10-minute threshold, you'll see 6 warnings total.

Example with default 10-minute threshold:

```
$ ./runjobs -b ./scripts/long-task.sh -f jobs.txt

[WARNING] Job long-task.sh-3 has been running for 10m0s: ./scripts/long-task.sh --verbose task3

[WARNING] Job long-task.sh-3 has been running for 20m0s: ./scripts/long-task.sh --verbose task3

[WARNING] Job long-task.sh-3 has been running for 30m0s: ./scripts/long-task.sh --verbose task3
```

Custom threshold example (5 minutes):

```
$ ./runjobs -b ./scripts/task.sh -f jobs.txt -w 300

[WARNING] Job task.sh-1 has been running for 5m0s: ./scripts/task.sh arg1
[WARNING] Job task.sh-1 has been running for 10m0s: ./scripts/task.sh arg1
[WARNING] Job task.sh-1 has been running for 15m0s: ./scripts/task.sh arg1
```

### Summary

After all jobs complete, a summary line is printed:

```
jobs total=10 success=9 failed=1
```

The program exits with code 1 if any job fails; otherwise 0.

## Signals

Ctrl-C (SIGINT) or SIGTERM cancels all running jobs gracefully.


