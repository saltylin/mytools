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
./runjobs -b /path/to/your_binary -f args.txt -p 4 -x
```

- `-b`: Executable path (for example, a bash script) run for each job.
- `-f`: Text file where each non-empty line is trimmed and split on whitespace into positional arguments for one job. Use `-` to read from stdin.
- `-a`: Shared argument appended to every job (repeat the flag as needed).
- `-p`: Maximum number of jobs to run at the same time (default: 4).
- `-x`: Cancel remaining jobs when any job fails.
- `-C`: Change to this directory before running jobs.
- `-V`: Print version and exit.

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
./runjobs -b ./scripts/run.sh -f args.txt -p 3 -a --verbose -a --flag=123
```

This launches:

```
./scripts/run.sh --verbose --flag=123 alpha
./scripts/run.sh --verbose --flag=123 beta
./scripts/run.sh --verbose --flag=123 foo bar baz
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


