# Python Tools

This directory contains Python-based command-line tools.

## Tools

### joinfiles.py

SQL-like left join for text files based on field matching.

**Usage:**
```bash
./joinfiles.py file1.txt file2.txt -k index1,index2 [-o output.txt]
```

**Description:**
Performs a left join operation on two text files where each line contains whitespace-separated fields. For each line in file1, looks up matching lines in file2 based on field values at specified indexes (1-based). If matches are found, concatenates the lines; if no matches, outputs the original file1 line.

**Arguments:**
- `file1.txt`: First input file (left side of join)
- `file2.txt`: Second input file (right side of join) 
- `-k, --keys`: Join keys as "index1,index2" where index1 is field in file1 and index2 is field in file2 (1-based)
- `-o, --output`: Output file (default: joins.txt)

**Examples:**
```bash
# Join employee.txt with department.txt where employee's dept_id (field 3) 
# matches department's id (field 1)
./joinfiles.py employee.txt department.txt -k 3,1 -o employee_with_dept.txt

# Join file1.txt and file2.txt on field 1 of file1 matching field 2 of file2
./joinfiles.py file1.txt file2.txt -k 1,2
```

**Features:**
- Handles both space and tab separators
- Preserves original whitespace format from file1
- Multiple matches create multiple output lines
- Progress reporting to stderr
- Proper error handling for missing files/fields

## Setup

### Prerequisites
- Python 3.7+ required
- pip3 for package management (if external dependencies are needed)

### Installation

1. **Install dependencies (if any):**
```bash
cd py
pip3 install -r requirements.txt
```

2. **Make scripts executable (optional):**
```bash
chmod +x *.py
```

### Usage

```bash
python3 tool_name.py [options]
# or if executable:
./tool_name.py [options]
```

### Adding New Dependencies

When adding tools that require external packages:
1. Install the package: `pip3 install package_name`
2. Add to requirements.txt manually with version pinning
