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
./runjobs -b /path/to/your_binary [-f jobs.txt | --] [-p 4] [-x] [-C dir] [-e] [-a shared1 shared2 ... [--]]
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

Stdout and stderr from each process are streamed directly without additional prefixes:

```
total 64
drwxr-xr-x   1 root root 4096 .
example error
```

After all jobs complete a summary line is printed:

```
jobs total=10 success=9 failed=1
```

The program exits with code 1 if any job fails; otherwise 0.

## Signals

Ctrl-C (SIGINT) or SIGTERM cancels all running jobs gracefully.


