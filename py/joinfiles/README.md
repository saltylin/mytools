# joinfiles

SQL-like left join for text files based on field matching.

## Usage

```bash
python3 joinfiles.py file1.txt file2.txt -k index1,index2 [-o output.txt]
```

## Description

Performs a left join operation on two text files where each line contains whitespace-separated fields. For each line in file1, looks up matching lines in file2 based on field values at specified indexes (1-based). If matches are found, concatenates the lines; if no matches, outputs the original file1 line.

## Arguments

- `file1.txt`: First input file (left side of join)
- `file2.txt`: Second input file (right side of join) 
- `-k, --keys`: Join keys as "index1,index2" where index1 is field in file1 and index2 is field in file2 (1-based)
- `-o, --output`: Output file (default: joins.txt)

## Examples

```bash
# Join employee.txt with department.txt where employee's dept_id (field 3) 
# matches department's id (field 1)
python3 joinfiles.py employee.txt department.txt -k 3,1 -o employee_with_dept.txt

# Join file1.txt and file2.txt on field 1 of file1 matching field 2 of file2
python3 joinfiles.py file1.txt file2.txt -k 1,2
```

## Features

- **Order Preservation**: Output maintains the exact order of lines from the first file
- **Smart Separator Handling**: Automatically detects and handles space, tab, and mixed separators
- **Intelligent Join Logic**: Uses tabs when either file uses tabs, otherwise preserves the most specific separator
- **Multiple Match Support**: Creates multiple output lines when file2 has multiple matches
- **Guaranteed Output**: Every line from file1 produces at least one output line (even if no matches found)
- **Comprehensive Reporting**: Shows detected separators and detailed join statistics
- **Error Handling**: Graceful handling of missing files, invalid field indexes, and malformed data
- **Progress Feedback**: Real-time progress reporting to stderr

## Installation

Make the script executable:
```bash
chmod +x joinfiles.py
```

Then run directly:
```bash
./joinfiles.py file1.txt file2.txt -k 1,2
```

## Separator Handling

The tool intelligently handles different separators between files:

1. **Tab Priority**: If either file uses tabs, the output will use tabs for consistency
2. **Specific Separators**: Non-space separators are preserved when possible  
3. **Fallback**: Defaults to single space if both files use spaces
4. **Detection Feedback**: Shows detected separators for both files during processing

**Example with Mixed Separators:**
```bash
# File1 uses spaces, File2 uses tabs → Output uses tabs
python3 joinfiles.py employees.txt departments.tsv -k 3,1
```

## Order Preservation

The tool **guarantees** that output lines appear in the same order as the first file:

- **Sequential Processing**: File1 is processed line by line from top to bottom
- **Order Maintained**: Output line order exactly matches File1 line order
- **Multiple Matches**: When File2 has multiple matches, they appear consecutively but maintain File1's position
- **No Matches**: Unmatched File1 lines still appear in their original position

**Example:**
```
File1:           File2:           Output:
emp003 Sales  →  Sales Dept1  →  emp003 Sales Sales Dept1
emp001 IT        Sales Dept2     emp003 Sales Sales Dept2  
emp002 Sales     IT Info         emp001 IT IT Info
                                 emp002 Sales Sales Dept1
                                 emp002 Sales Sales Dept2
```

Notice how `emp003`, `emp001`, `emp002` appear in output in the same order as File1, even though `emp002` and `emp003` both match "Sales".
