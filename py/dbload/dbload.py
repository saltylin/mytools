#!/usr/bin/env python3
"""
dbload - Interactive Database Loader CLI Tool

A command-line tool that makes it easy to load data files into a SQLite database
with automatic format detection and interactive schema confirmation.
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
import re

# Import readline for command history and arrow key support
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False


class DataTypeDetector:
    """Detects appropriate SQLite data types for column values."""
    
    @staticmethod
    def detect_type(values: List[str]) -> str:
        """
        Detect the most appropriate SQLite type for a list of string values.
        
        Args:
            values: List of string values from a column
            
        Returns:
            SQLite type: 'INTEGER', 'REAL', or 'TEXT'
        """
        if not values:
            return 'TEXT'
        
        # Filter out empty/null values for type detection
        non_empty_values = [v.strip() for v in values if v.strip()]
        if not non_empty_values:
            return 'TEXT'
        
        # Check if all values are integers
        integer_count = 0
        real_count = 0
        
        for value in non_empty_values:
            # Try integer first
            try:
                int(value)
                integer_count += 1
                continue
            except ValueError:
                pass
            
            # Try float
            try:
                float(value)
                real_count += 1
                continue
            except ValueError:
                pass
        
        total_numeric = integer_count + real_count
        total_values = len(non_empty_values)
        
        # If 80% or more are numeric, consider it numeric
        if total_numeric / total_values >= 0.8:
            # If all numeric values are integers, use INTEGER
            if real_count == 0:
                return 'INTEGER'
            else:
                return 'REAL'
        
        return 'TEXT'


class FileFormatDetector:
    """Detects file format and extracts data with headers."""
    
    @staticmethod
    def detect_csv_delimiter(file_path: str, sample_size: int = 5) -> str:
        """
        Detect the most likely CSV delimiter by analyzing the first few lines.
        
        Args:
            file_path: Path to the CSV file
            sample_size: Number of lines to analyze
            
        Returns:
            Most likely delimiter character
        """
        delimiters = [',', ';', '|', '\t']
        delimiter_scores = {delim: 0 for delim in delimiters}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                sample_lines = []
                for _ in range(sample_size):
                    line = f.readline()
                    if not line:
                        break
                    sample_lines.append(line.strip())
            
            for delimiter in delimiters:
                field_counts = []
                for line in sample_lines:
                    if line:
                        fields = line.split(delimiter)
                        field_counts.append(len(fields))
                
                if field_counts:
                    # Score based on consistency of field count and reasonable number of fields
                    avg_fields = sum(field_counts) / len(field_counts)
                    consistency = 1.0 - (max(field_counts) - min(field_counts)) / max(avg_fields, 1)
                    
                    # Prefer delimiters that create 2+ fields consistently
                    if avg_fields >= 2:
                        delimiter_scores[delimiter] = consistency * avg_fields
        
        except Exception:
            return ','  # Default fallback
        
        # Return delimiter with highest score
        best_delimiter = max(delimiter_scores.items(), key=lambda x: x[1])[0]
        return best_delimiter if delimiter_scores[best_delimiter] > 0 else ','
    
    @staticmethod
    def load_csv(file_path: str) -> Tuple[List[str], List[List[str]], bool, List[List[str]]]:
        """
        Load CSV file and detect headers.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Tuple of (headers, rows, has_headers_flag, all_raw_rows)
        """
        delimiter = FileFormatDetector.detect_csv_delimiter(file_path)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read first few lines to detect headers
            sample_lines = []
            for _ in range(10):
                line = f.readline()
                if not line:
                    break
                sample_lines.append(line.strip())
            
            if not sample_lines:
                return [], [], False
        
        # Use csv.Sniffer to help detect headers
        sample_text = '\n'.join(sample_lines)
        sniffer = csv.Sniffer()
        
        try:
            has_headers = sniffer.has_header(sample_text)
        except Exception:
            # Fallback: assume headers if first row looks non-numeric
            first_row = sample_lines[0].split(delimiter) if sample_lines else []
            has_headers = any(not FileFormatDetector._looks_like_number(field.strip()) 
                            for field in first_row)
        
        # Read the entire file
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=delimiter)
            all_rows = list(reader)
        
        if not all_rows:
            return [], [], False, []
        
        if has_headers:
            headers = all_rows[0]
            data_rows = all_rows[1:]
        else:
            headers = [f'column_{i+1}' for i in range(len(all_rows[0]))]
            data_rows = all_rows
        
        return headers, data_rows, has_headers, all_rows
    
    @staticmethod
    def load_json(file_path: str) -> Tuple[List[str], List[List[str]], bool, List[List[str]]]:
        """
        Load JSON file (array of objects or newline-delimited).
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Tuple of (headers, rows, has_headers_flag, all_raw_rows)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Try parsing as regular JSON first
            try:
                data = json.loads(content)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    # Array of objects
                    headers = list(data[0].keys())
                    rows = []
                    for obj in data:
                        row = [str(obj.get(header, '')) for header in headers]
                        rows.append(row)
                    return headers, rows, True, rows
            except json.JSONDecodeError:
                pass
            
            # Try newline-delimited JSON
            lines = content.split('\n')
            objects = []
            for line in lines:
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            objects.append(obj)
                    except json.JSONDecodeError:
                        continue
            
            if objects:
                # Collect all unique keys
                all_keys = set()
                for obj in objects:
                    all_keys.update(obj.keys())
                
                headers = sorted(list(all_keys))
                rows = []
                for obj in objects:
                    row = [str(obj.get(header, '')) for header in headers]
                    rows.append(row)
                
                return headers, rows, True, rows
        
        except Exception as e:
            raise ValueError(f"Failed to parse JSON file: {e}")
        
        return [], [], False, []
    
    @staticmethod
    def load_text(file_path: str) -> Tuple[List[str], List[List[str]], bool, List[List[str]]]:
        """
        Load whitespace/tab-separated text file.
        
        Args:
            file_path: Path to text file
            
        Returns:
            Tuple of (headers, rows, has_headers_flag, all_raw_rows)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
        
        if not lines:
            return [], [], False
        
        # Split by whitespace
        all_rows = []
        for line in lines:
            # Split by any whitespace, but preserve quoted strings
            fields = re.findall(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', line)
            # Remove quotes if present
            fields = [field.strip('\'"') for field in fields]
            if fields:
                all_rows.append(fields)
        
        if not all_rows:
            return [], [], False, []
        
        # Detect headers (assume first row is headers if it looks non-numeric)
        first_row = all_rows[0]
        has_headers = any(not FileFormatDetector._looks_like_number(field) 
                         for field in first_row)
        
        if has_headers:
            headers = first_row
            data_rows = all_rows[1:]
        else:
            headers = [f'column_{i+1}' for i in range(len(first_row))]
            data_rows = all_rows
        
        return headers, data_rows, has_headers, all_rows
    
    @staticmethod
    def _looks_like_number(value: str) -> bool:
        """Check if a string looks like a number."""
        try:
            float(value.strip())
            return True
        except ValueError:
            return False
    
    @staticmethod
    def detect_and_load(file_path: str) -> Tuple[List[str], List[List[str]], bool, str, List[List[str]]]:
        """
        Auto-detect file format and load data.
        
        Args:
            file_path: Path to data file
            
        Returns:
            Tuple of (headers, rows, has_headers_flag, detected_format, all_raw_rows)
        """
        file_ext = Path(file_path).suffix.lower()
        
        # Try format detection based on extension first
        if file_ext == '.csv':
            try:
                headers, rows, has_headers, all_rows = FileFormatDetector.load_csv(file_path)
                return headers, rows, has_headers, 'CSV', all_rows
            except Exception:
                pass
        
        elif file_ext == '.json':
            try:
                headers, rows, has_headers, all_rows = FileFormatDetector.load_json(file_path)
                return headers, rows, has_headers, 'JSON', all_rows
            except Exception:
                pass
        
        elif file_ext in ['.txt', '.tsv', '.dat']:
            try:
                headers, rows, has_headers, all_rows = FileFormatDetector.load_text(file_path)
                return headers, rows, has_headers, 'TEXT', all_rows
            except Exception:
                pass
        
        # Fallback: try each format
        formats_to_try = [
            ('CSV', FileFormatDetector.load_csv),
            ('JSON', FileFormatDetector.load_json),
            ('TEXT', FileFormatDetector.load_text)
        ]
        
        for format_name, loader_func in formats_to_try:
            try:
                headers, rows, has_headers, all_rows = loader_func(file_path)
                if headers and rows:
                    return headers, rows, has_headers, format_name, all_rows
            except Exception:
                continue
        
        raise ValueError(f"Could not detect format or parse file: {file_path}")


class SchemaManager:
    """Manages schema detection and user confirmation."""
    
    @staticmethod
    def get_table_name(default_name: str, file_path: str) -> str:
        """
        Get table name from user with confirmation.
        
        Args:
            default_name: Default table name (from filename or --table arg)
            file_path: Path to the source file
            
        Returns:
            Confirmed table name
        """
        print(f"\n📋 Table Name Configuration")
        print(f"Source file: {file_path}")
        print("=" * 50)
        
        while True:
            try:
                table_name = input(f"Table name [{default_name}]: ").strip()
                
                if not table_name:
                    table_name = default_name
                
                # Validate table name (basic SQLite naming rules)
                if not table_name:
                    print("❌ Table name cannot be empty")
                    continue
                
                # Check for valid characters (letters, numbers, underscore)
                import re
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
                    print("❌ Table name must start with letter/underscore and contain only letters, numbers, underscores")
                    continue
                
                # Check for SQLite reserved words (basic list)
                reserved_words = {
                    'table', 'index', 'select', 'insert', 'update', 'delete', 'create', 'drop',
                    'alter', 'where', 'from', 'join', 'order', 'group', 'having', 'union'
                }
                if table_name.lower() in reserved_words:
                    print(f"❌ '{table_name}' is a reserved SQL keyword. Please choose a different name.")
                    continue
                
                return table_name
                
            except KeyboardInterrupt:
                print("\n\nOperation cancelled by user.")
                sys.exit(0)
    
    @staticmethod
    def confirm_headers(headers: List[str], first_data_row: List[str]) -> Tuple[List[str], bool]:
        """
        Confirm if detected headers are actually headers or data.
        
        Args:
            headers: Detected header row
            first_data_row: First data row (or second row if headers detected)
            
        Returns:
            Tuple of (confirmed_headers, headers_confirmed)
        """
        print(f"\n🔍 Header Detection")
        print("=" * 50)
        print("Detected first line as headers:")
        for i, header in enumerate(headers, 1):
            print(f"  {i}. {header}")
        
        if first_data_row:
            print("\nFirst data row:")
            for i, value in enumerate(first_data_row, 1):
                print(f"  {i}. {value}")
        
        print("=" * 50)
        
        while True:
            try:
                choice = input("\nAre these correct field names? (y/n): ").lower().strip()
                
                if choice in ['y', 'yes']:
                    return headers, True
                elif choice in ['n', 'no']:
                    return SchemaManager._get_manual_headers(len(headers)), False
                else:
                    print("Please enter 'y' (yes) or 'n' (no)")
            except KeyboardInterrupt:
                print("\n\nOperation cancelled by user.")
                sys.exit(0)
    
    @staticmethod
    def _get_manual_headers(num_fields: int) -> List[str]:
        """Get field names manually from user."""
        print(f"\n📝 Manual Field Names Entry")
        print(f"Please enter {num_fields} field names:")
        
        headers = []
        try:
            for i in range(num_fields):
                while True:
                    name = input(f"  Field {i+1} name: ").strip()
                    if name:
                        headers.append(name)
                        break
                    else:
                        print("    Field name cannot be empty")
        except KeyboardInterrupt:
            print("\n\nField name entry cancelled by user.")
            sys.exit(0)
        
        return headers
    
    @staticmethod
    def detect_schema(headers: List[str], rows: List[List[str]]) -> List[Dict[str, Any]]:
        """
        Detect schema from headers and sample data.
        
        Args:
            headers: Column headers
            rows: Data rows
            
        Returns:
            List of column schema dictionaries
        """
        schema = []
        
        for i, header in enumerate(headers):
            # Get sample values for this column
            column_values = []
            for row in rows[:100]:  # Sample first 100 rows
                if i < len(row):
                    column_values.append(row[i])
            
            # Detect data type
            data_type = DataTypeDetector.detect_type(column_values)
            
            # Get preview values (first 3-5 non-empty values)
            preview_values = []
            for value in column_values:
                if value.strip() and len(preview_values) < 5:
                    preview_values.append(value.strip())
            
            schema.append({
                'name': header.strip(),
                'type': data_type,
                'preview': preview_values
            })
        
        return schema
    
    @staticmethod
    def display_schema(schema: List[Dict[str, Any]], detected_format: str) -> None:
        """Display detected schema to user."""
        print(f"\n📊 Detected {detected_format} format with {len(schema)} fields:")
        print("=" * 60)
        
        for i, col in enumerate(schema, 1):
            preview_str = ", ".join(f"'{v}'" for v in col['preview'][:3])
            if len(col['preview']) > 3:
                preview_str += "..."
            
            print(f"{i:2d}. {col['name']:<20} ({col['type']:<8}) Sample: {preview_str}")
        
        print("=" * 60)
    
    @staticmethod
    def confirm_schema(schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Allow user to confirm or modify schema.
        
        Args:
            schema: Detected schema
            
        Returns:
            Confirmed/modified schema
        """
        while True:
            try:
                choice = input("\nProceed with import? (y/n/edit): ").lower().strip()
                
                if choice in ['y', 'yes']:
                    return schema
                elif choice in ['n', 'no']:
                    print("Import cancelled.")
                    sys.exit(0)
                elif choice in ['e', 'edit']:
                    return SchemaManager._edit_schema(schema)
                else:
                    print("Please enter 'y' (yes), 'n' (no), or 'edit'")
            except KeyboardInterrupt:
                print("\n\nImport cancelled by user.")
                sys.exit(0)
    
    @staticmethod
    def _edit_schema(schema: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Interactive schema editing."""
        print("\n✏️  Schema Editor")
        print("Available types: TEXT, INTEGER, REAL")
        print("Press Enter to keep current value, or type new value to change")
        print("-" * 50)
        
        try:
            for i, col in enumerate(schema):
                print(f"\nField {i+1}:")
                
                # Edit name
                new_name = input(f"  Name [{col['name']}]: ").strip()
                if new_name:
                    col['name'] = new_name
                
                # Edit type
                while True:
                    new_type = input(f"  Type [{col['type']}]: ").strip().upper()
                    if not new_type:
                        break
                    elif new_type in ['TEXT', 'INTEGER', 'REAL']:
                        col['type'] = new_type
                        break
                    else:
                        print("    Invalid type. Use: TEXT, INTEGER, or REAL")
            
            print("\n✅ Schema updated!")
            SchemaManager.display_schema(schema, "EDITED")
            
        except KeyboardInterrupt:
            print("\n\nSchema editing cancelled by user.")
            sys.exit(0)
        
        return schema


class DatabaseManager:
    """Manages SQLite database operations."""
    
    def __init__(self, db_path: str):
        """Initialize database manager."""
        self.db_path = db_path
        self.conn = None
    
    def connect(self) -> None:
        """Connect to SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Enable column access by name
            print(f"📁 Connected to database: {self.db_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to database: {e}")
    
    def create_table(self, table_name: str, schema: List[Dict[str, Any]]) -> None:
        """
        Create table with given schema.
        
        Args:
            table_name: Name of table to create
            schema: List of column definitions
        """
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        # Sanitize table name
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name)
        
        # Build CREATE TABLE statement
        columns = []
        for col in schema:
            col_name = re.sub(r'[^a-zA-Z0-9_]', '_', col['name'])
            columns.append(f'"{col_name}" {col["type"]}')
        
        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(columns)})'
        
        try:
            self.conn.execute(create_sql)
            self.conn.commit()
            print(f"📋 Created table: {table_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to create table: {e}")
    
    def insert_data(self, table_name: str, schema: List[Dict[str, Any]], 
                   rows: List[List[str]]) -> None:
        """
        Insert data into table with progress indication.
        
        Args:
            table_name: Target table name
            schema: Table schema
            rows: Data rows to insert
        """
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        if not rows:
            print("⚠️  No data to insert")
            return
        
        # Sanitize names
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name)
        col_names = [re.sub(r'[^a-zA-Z0-9_]', '_', col['name']) for col in schema]
        
        # Build INSERT statement
        placeholders = ', '.join(['?' for _ in col_names])
        quoted_cols = ', '.join([f'"{name}"' for name in col_names])
        insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES ({placeholders})'
        
        print(f"📥 Importing {len(rows)} rows...")
        
        try:
            # Insert in batches for better performance
            batch_size = 1000
            imported = 0
            
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                
                # Prepare batch data
                batch_data = []
                for row in batch:
                    # Pad row if necessary and convert types
                    padded_row = row + [''] * (len(schema) - len(row))
                    converted_row = []
                    
                    for j, (value, col) in enumerate(zip(padded_row[:len(schema)], schema)):
                        converted_value = self._convert_value(value, col['type'])
                        converted_row.append(converted_value)
                    
                    batch_data.append(converted_row)
                
                self.conn.executemany(insert_sql, batch_data)
                imported += len(batch)
                
                # Show progress
                if len(rows) > 1000:
                    progress = (imported / len(rows)) * 100
                    print(f"  Progress: {imported}/{len(rows)} ({progress:.1f}%)")
            
            self.conn.commit()
            print(f"✅ Successfully imported {imported} rows into table '{table_name}'")
            
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"Failed to insert data: {e}")
    
    def _convert_value(self, value: str, target_type: str) -> Union[str, int, float, None]:
        """Convert string value to appropriate Python type."""
        if not value or not value.strip():
            return None
        
        value = value.strip()
        
        try:
            if target_type == 'INTEGER':
                return int(float(value))  # Handle "1.0" -> 1
            elif target_type == 'REAL':
                return float(value)
            else:  # TEXT
                return value
        except (ValueError, TypeError):
            # If conversion fails, store as text
            return value
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in database."""
        if not self.conn:
            return []
        
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        return [row[0] for row in cursor.fetchall()]
    
    def get_table_schema(self, table_name: str) -> List[Tuple[str, str]]:
        """Get schema for a specific table."""
        if not self.conn:
            return []
        
        cursor = self.conn.execute(f'PRAGMA table_info("{table_name}")')
        return [(row[1], row[2]) for row in cursor.fetchall()]  # (name, type)
    
    def execute_query(self, query: str) -> List[sqlite3.Row]:
        """Execute SQL query and return results."""
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        try:
            cursor = self.conn.execute(query)
            return cursor.fetchall()
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


class SQLInterface:
    """Interactive SQL query interface."""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize SQL interface."""
        self.db_manager = db_manager
        self._setup_readline()
    
    def _setup_readline(self) -> None:
        """Setup readline for command history and editing."""
        if not READLINE_AVAILABLE:
            return
        
        # Enable tab completion for SQL keywords and table names
        readline.set_completer(self._sql_completer)
        readline.parse_and_bind("tab: complete")
        
        # Set history file
        history_file = os.path.expanduser("~/.dbload_history")
        try:
            readline.read_history_file(history_file)
        except FileNotFoundError:
            pass  # No history file yet
        
        # Limit history size
        readline.set_history_length(1000)
        
        # Save history on exit
        import atexit
        atexit.register(self._save_history, history_file)
    
    def _save_history(self, history_file: str) -> None:
        """Save command history to file."""
        if READLINE_AVAILABLE:
            try:
                readline.write_history_file(history_file)
            except Exception:
                pass  # Ignore errors when saving history
    
    def _sql_completer(self, text: str, state: int) -> Optional[str]:
        """Tab completion for SQL keywords and table names."""
        if not text:
            return None
        
        # SQL keywords for completion
        sql_keywords = [
            'SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP',
            'ALTER', 'INDEX', 'TABLE', 'DATABASE', 'ORDER', 'BY', 'GROUP', 'HAVING',
            'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'UNION', 'DISTINCT', 'COUNT',
            'SUM', 'AVG', 'MAX', 'MIN', 'AS', 'AND', 'OR', 'NOT', 'IN', 'LIKE',
            'BETWEEN', 'IS', 'NULL', 'TRUE', 'FALSE', 'LIMIT', 'OFFSET'
        ]
        
        # Get table names
        try:
            tables = self.db_manager.get_tables()
        except Exception:
            tables = []
        
        # Combine keywords and table names
        candidates = sql_keywords + [t.upper() for t in tables] + tables
        
        # Filter matches
        matches = [cmd for cmd in candidates if cmd.upper().startswith(text.upper())]
        
        if state < len(matches):
            return matches[state]
        return None
    
    def run(self) -> None:
        """Run interactive SQL prompt."""
        print("\n🔍 Interactive SQL Query Interface")
        if READLINE_AVAILABLE:
            print("✅ Command history and arrow keys enabled")
        else:
            print("⚠️  Install 'readline' for command history support")
        print("Enter SQL queries or meta-commands:")
        print("  .tables     - List all tables")
        print("  .schema <table> - Show table structure")
        print("  .exit/.quit - Exit")
        print("-" * 50)
        
        while True:
            try:
                query = input("sql> ").strip()
                
                if not query:
                    continue
                
                # Handle meta-commands
                if query.startswith('.'):
                    if query in ['.exit', '.quit']:
                        print("Goodbye!")
                        break
                    elif query == '.tables':
                        self._show_tables()
                    elif query.startswith('.schema'):
                        parts = query.split()
                        if len(parts) > 1:
                            self._show_schema(parts[1])
                        else:
                            print("Usage: .schema <table_name>")
                    else:
                        print(f"Unknown command: {query}")
                    continue
                
                # Execute SQL query
                results = self.db_manager.execute_query(query)
                self._display_results(results)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def _show_tables(self) -> None:
        """Show all tables in database."""
        tables = self.db_manager.get_tables()
        if tables:
            print("\nTables:")
            for table in tables:
                print(f"  {table}")
        else:
            print("No tables found in database.")
    
    def _show_schema(self, table_name: str) -> None:
        """Show schema for specific table."""
        schema = self.db_manager.get_table_schema(table_name)
        if schema:
            print(f"\nSchema for table '{table_name}':")
            for col_name, col_type in schema:
                print(f"  {col_name:<20} {col_type}")
        else:
            print(f"Table '{table_name}' not found.")
    
    def _display_results(self, results: List[sqlite3.Row]) -> None:
        """Display query results in a readable table format."""
        if not results:
            print("No results.")
            return
        
        # Get column names
        columns = list(results[0].keys())
        
        # Calculate column widths
        col_widths = {}
        for col in columns:
            col_widths[col] = len(col)
        
        for row in results:
            for col in columns:
                value_str = str(row[col]) if row[col] is not None else 'NULL'
                col_widths[col] = max(col_widths[col], len(value_str))
        
        # Print header
        header_parts = []
        separator_parts = []
        for col in columns:
            width = min(col_widths[col], 30)  # Max width of 30
            header_parts.append(f"{col:<{width}}")
            separator_parts.append("-" * width)
        
        print("\n" + " | ".join(header_parts))
        print("-+-".join(separator_parts))
        
        # Print rows
        for row in results[:100]:  # Limit to first 100 rows
            row_parts = []
            for col in columns:
                value_str = str(row[col]) if row[col] is not None else 'NULL'
                width = min(col_widths[col], 30)
                if len(value_str) > width:
                    value_str = value_str[:width-3] + "..."
                row_parts.append(f"{value_str:<{width}}")
            print(" | ".join(row_parts))
        
        if len(results) > 100:
            print(f"\n... and {len(results) - 100} more rows")
        
        print(f"\n({len(results)} rows)")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Interactive Database Loader - Load data files into SQLite with auto-detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - auto-detect everything
  python dbload.py data.csv
  
  # Specify database name
  python dbload.py data.csv --db mydata.db
  
  # Specify table name
  python dbload.py data.csv --table users
  
  # Load multiple files
  python dbload.py file1.csv file2.json --db combined.db

Supported formats:
  - CSV files (comma, semicolon, pipe delimited)
  - JSON files (array of objects or newline-delimited)
  - Text files (whitespace/tab separated)
        """)
    
    parser.add_argument('files', nargs='+', help='Data files to load')
    parser.add_argument('--db', default='data.db', 
                       help='Database file name (default: data.db)')
    parser.add_argument('--table', 
                       help='Table name (default: filename without extension)')
    
    args = parser.parse_args()
    
    # Initialize database manager
    db_manager = DatabaseManager(args.db)
    
    try:
        db_manager.connect()
        
        # Process each file
        for file_path in args.files:
            if not os.path.exists(file_path):
                print(f"❌ File not found: {file_path}")
                continue
            
            print(f"\n🔍 Processing file: {file_path}")
            
            try:
                # Detect format and load data
                headers, rows, has_headers, detected_format, all_rows = FileFormatDetector.detect_and_load(file_path)
                
                if not headers or not rows:
                    print(f"⚠️  No data found in {file_path}")
                    continue
                
                # Confirm headers with user if auto-detected
                if has_headers and len(all_rows) > 1:
                    # Show first row as headers and second row as data for confirmation
                    confirmed_headers, headers_confirmed = SchemaManager.confirm_headers(
                        headers, all_rows[1] if len(all_rows) > 1 else []
                    )
                    
                    if not headers_confirmed:
                        # User said first row is data, not headers
                        # Use all rows as data and confirmed_headers as field names
                        headers = confirmed_headers
                        rows = all_rows
                elif not has_headers:
                    # No headers detected, ask user for field names
                    if all_rows:
                        print(f"\n🔍 No headers detected in {detected_format} file")
                        print("First row appears to be data:")
                        for i, value in enumerate(all_rows[0], 1):
                            print(f"  {i}. {value}")
                        
                        headers = SchemaManager._get_manual_headers(len(all_rows[0]))
                        rows = all_rows
                
                # Detect schema
                schema = SchemaManager.detect_schema(headers, rows)
                
                # Display and confirm schema
                SchemaManager.display_schema(schema, detected_format)
                confirmed_schema = SchemaManager.confirm_schema(schema)
                
                # Determine table name with interactive prompt
                if args.table:
                    default_table_name = args.table
                else:
                    default_table_name = Path(file_path).stem
                
                table_name = SchemaManager.get_table_name(default_table_name, file_path)
                
                # Create table and import data
                db_manager.create_table(table_name, confirmed_schema)
                db_manager.insert_data(table_name, confirmed_schema, rows)
                
            except Exception as e:
                print(f"❌ Error processing {file_path}: {e}")
                continue
        
        # Start interactive SQL interface
        sql_interface = SQLInterface(db_manager)
        sql_interface.run()
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        db_manager.close()


if __name__ == '__main__':
    main()
