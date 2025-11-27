#!/usr/bin/env python3
"""
joinfiles - SQL-like left join for text files based on field matching

Performs a left join operation on two text files where each line contains
whitespace-separated fields. Joins lines based on matching field values
at specified column indexes.
"""

import argparse
import sys
import re
from collections import defaultdict
from typing import List, Dict, Tuple, Optional


def detect_separator(line: str) -> str:
    """Detect the primary whitespace separator used in a line (space or tab)."""
    if '\t' in line:
        return '\t'
    return ' '


def split_fields(line: str) -> List[str]:
    """Split a line into fields by any whitespace, preserving field order."""
    return line.strip().split()


def get_field_value(fields: List[str], index: int) -> Optional[str]:
    """Get field value at 1-based index, return None if index is out of range."""
    if index < 1 or index > len(fields):
        return None
    return fields[index - 1]


def build_lookup_index(file_path: str, key_index: int) -> Tuple[Dict[str, List[str]], str]:
    """
    Build a lookup index for the second file.
    Returns (lookup_dict, separator) where lookup_dict maps key values to lists of full lines.
    """
    lookup = defaultdict(list)
    separator = ' '  # default
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.rstrip('\n\r')
                if not line.strip():  # Skip empty lines
                    continue
                
                # Detect separator from first non-empty line
                if line_num == 1:
                    separator = detect_separator(line)
                
                fields = split_fields(line)
                key_value = get_field_value(fields, key_index)
                
                if key_value is not None:
                    lookup[key_value].append(line)
                else:
                    print(f"Warning: Line {line_num} in {file_path} has no field at index {key_index}", 
                          file=sys.stderr)
    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)
    
    return dict(lookup), separator


def join_files(file1_path: str, file2_path: str, index1: int, index2: int, output_path: str):
    """Perform the left join operation between two files."""
    
    # Build lookup index for file2
    print(f"Building lookup index for {file2_path}...", file=sys.stderr)
    file2_lookup, file2_separator = build_lookup_index(file2_path, index2)
    
    # Count lines in file2 for summary
    file2_total_lines = 0
    try:
        with open(file2_path, 'r', encoding='utf-8') as f2:
            for line in f2:
                if line.strip():  # Count non-empty lines
                    file2_total_lines += 1
    except IOError:
        pass  # Error already handled in build_lookup_index
    
    # Process file1 and perform joins
    print(f"Processing {file1_path} and writing results to {output_path}...", file=sys.stderr)
    print(f"Detected separator in {file2_path}: {'TAB' if file2_separator == chr(9) else repr(file2_separator)}", file=sys.stderr)
    
    try:
        with open(file1_path, 'r', encoding='utf-8') as f1, \
             open(output_path, 'w', encoding='utf-8') as out:
            
            file1_separator = ' '  # default
            file1_total_lines = 0
            file1_processed_lines = 0  # Lines that had valid join key
            matched_lines = 0          # Lines from file1 that found matches
            unmatched_lines = 0        # Lines from file1 that found no matches
            total_output_lines = 0     # Total lines written to output
            
            for line_num, line in enumerate(f1, 1):
                line = line.rstrip('\n\r')
                if not line.strip():  # Skip empty lines
                    continue
                
                file1_total_lines += 1
                
                # Detect separator from first non-empty line
                if file1_total_lines == 1:
                    file1_separator = detect_separator(line)
                    print(f"Detected separator in {file1_path}: {'TAB' if file1_separator == chr(9) else repr(file1_separator)}", file=sys.stderr)
                
                fields = split_fields(line)
                key_value = get_field_value(fields, index1)
                
                if key_value is None:
                    print(f"Warning: Line {line_num} in {file1_path} has no field at index {index1}", 
                          file=sys.stderr)
                    # Output the original line (ensures every file1 line produces output)
                    out.write(line + '\n')
                    total_output_lines += 1
                    unmatched_lines += 1
                    continue
                
                file1_processed_lines += 1
                
                # Look up matching lines in file2
                matching_lines = file2_lookup.get(key_value, [])
                
                if not matching_lines:
                    # No match found, output original line from file1
                    out.write(line + '\n')
                    total_output_lines += 1
                    unmatched_lines += 1
                else:
                    # Join with each matching line from file2
                    matched_lines += 1
                    for match_line in matching_lines:
                        # Determine the best separator for joining
                        # Priority: 1) Tab if either file uses tab, 2) File1 separator, 3) Single space
                        if file1_separator == '\t' or file2_separator == '\t':
                            join_separator = '\t'
                        elif file1_separator != ' ':
                            join_separator = file1_separator
                        elif file2_separator != ' ':
                            join_separator = file2_separator
                        else:
                            join_separator = ' '  # Default fallback
                        
                        joined_line = line + join_separator + match_line
                        out.write(joined_line + '\n')
                        total_output_lines += 1
            
            # Print comprehensive summary
            print(f"\n=== JOIN SUMMARY ===", file=sys.stderr)
            print(f"File 1 ({file1_path}):", file=sys.stderr)
            print(f"  Total lines: {file1_total_lines}", file=sys.stderr)
            print(f"  Lines with valid join key: {file1_processed_lines}", file=sys.stderr)
            print(f"File 2 ({file2_path}):", file=sys.stderr)
            print(f"  Total lines: {file2_total_lines}", file=sys.stderr)
            print(f"  Unique join keys: {len(file2_lookup)}", file=sys.stderr)
            print(f"Join Results:", file=sys.stderr)
            print(f"  Matched lines from file1: {matched_lines}", file=sys.stderr)
            print(f"  Unmatched lines from file1: {unmatched_lines}", file=sys.stderr)
            print(f"  Total output lines: {total_output_lines}", file=sys.stderr)
            print(f"Output written to: {output_path}", file=sys.stderr)
    
    except FileNotFoundError:
        print(f"Error: File '{file1_path}' not found", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error processing files: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Perform SQL-like left join on two text files based on field matching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Join file1.txt and file2.txt on field 1 of file1 matching field 2 of file2
  %(prog)s file1.txt file2.txt -k 1,2
  
  # Same as above but specify output file
  %(prog)s file1.txt file2.txt -k 1,2 -o result.txt
  
  # Join employee.txt with department.txt where employee's dept_id (field 3) 
  # matches department's id (field 1)
  %(prog)s employee.txt department.txt -k 3,1 -o employee_with_dept.txt

Field indexes are 1-based (1 = first field, 2 = second field, etc.)
Fields are separated by whitespace (spaces or tabs).
Output uses the same separator as the first file.
        """)
    
    parser.add_argument('file1', help='First input file (left side of join)')
    parser.add_argument('file2', help='Second input file (right side of join)')
    parser.add_argument('-k', '--keys', required=True, 
                       help='Join keys as "index1,index2" where index1 is field in file1 and index2 is field in file2 (1-based)')
    parser.add_argument('-o', '--output', default='joins.txt', 
                       help='Output file (default: joins.txt)')
    
    args = parser.parse_args()
    
    # Parse and validate the keys argument
    try:
        key_parts = args.keys.split(',')
        if len(key_parts) != 2:
            raise ValueError("Keys must be in format 'index1,index2'")
        
        index1 = int(key_parts[0].strip())
        index2 = int(key_parts[1].strip())
        
        if index1 < 1:
            raise ValueError("index1 must be >= 1")
        if index2 < 1:
            raise ValueError("index2 must be >= 1")
            
    except ValueError as e:
        print(f"Error parsing keys argument: {e}", file=sys.stderr)
        print("Keys must be in format 'index1,index2' where both are positive integers", file=sys.stderr)
        sys.exit(1)
    
    # Perform the join
    join_files(args.file1, args.file2, index1, index2, args.output)


if __name__ == '__main__':
    main()
