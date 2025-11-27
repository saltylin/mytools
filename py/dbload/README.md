# dbload - Interactive Database Loader CLI Tool

A powerful Python command-line tool that makes it easy to load data files into a SQLite database with automatic format detection and interactive schema confirmation.

## Features

🔍 **Auto-Detection**: Automatically detects CSV, JSON, and text file formats  
📋 **Header Confirmation**: Interactive confirmation of field names vs. data detection  
📝 **Manual Field Entry**: Prompts for field names when no headers detected  
🏷️ **Table Name Prompt**: Interactive table name confirmation with validation  
📊 **Smart Schema**: Detects data types and provides interactive schema editing  
🎯 **User-Friendly**: Interactive prompts guide you through the import process  
⚡ **Fast Import**: Batch processing with progress indicators for large files  
🔧 **SQL Interface**: Built-in interactive SQL query interface with command history, tab completion, and graceful Ctrl-C handling  
📁 **Multi-Format**: Supports various delimiters and file structures  

## Supported File Formats

### CSV Files
- **Delimiters**: Comma, semicolon, pipe (`|`), tab
- **Headers**: Auto-detects presence of headers
- **Example**: `data.csv`, `users.csv`

### JSON Files  
- **Array of Objects**: `[{"name": "John", "age": 30}, ...]`
- **Newline-Delimited**: One JSON object per line
- **Example**: `data.json`, `records.jsonl`

### Text Files
- **Whitespace-Separated**: Space or tab delimited
- **Quoted Fields**: Handles quoted strings with spaces
- **Example**: `data.txt`, `log.tsv`, `export.dat`

## Installation

```bash
cd dbload
chmod +x dbload.py
```

## Usage

### Basic Usage

```bash
# Load a single file (auto-detect everything)
python3 dbload.py data.csv

# Or use directly if executable
./dbload.py data.csv
```

### Advanced Usage

```bash
# Specify custom database name
python3 dbload.py data.csv --db myproject.db

# Specify custom table name  
python3 dbload.py users.csv --table employees

# Load multiple files into same database
python3 dbload.py sales.csv products.json --db business.db

# Get help
python3 dbload.py --help
```

## Interactive Workflow

### 1. File Detection
```
🔍 Processing file: sales.csv
📊 Detected CSV format with 4 fields:
============================================================
 1. name                 (TEXT    ) Sample: 'John', 'Jane', 'Bob'
 2. age                  (INTEGER ) Sample: '25', '30', '35'
 3. city                 (TEXT    ) Sample: 'NYC', 'LA', 'Chicago'
 4. salary               (REAL    ) Sample: '50000.0', '75000.5'
============================================================
```

### 2. Header Confirmation
```
🔍 Header Detection
==================================================
Detected first line as headers:
  1. name
  2. age
  3. city
  4. salary

First data row:
  1. John
  2. 25
  3. NYC
  4. 50000
==================================================

Are these correct field names? (y/n): y
```

### 3. Schema Confirmation
```
Proceed with import? (y/n/edit): edit

✏️  Schema Editor
Available types: TEXT, INTEGER, REAL
Press Enter to keep current value, or type new value to change
--------------------------------------------------

Field 1:
  Name [name]: employee_name
  Type [TEXT]: 

Field 2:
  Name [age]: 
  Type [INTEGER]: 

Field 3:
  Name [city]: location
  Type [TEXT]: 

Field 4:
  Name [salary]: 
  Type [REAL]: 
```

### 4. Table Name Configuration
```
📋 Table Name Configuration
Source file: sales.csv
==================================================
Table name [sales]: employee_sales

📁 Connected to database: data.db
📋 Created table: employee_sales
```

### 5. Data Import
```
📥 Importing 1000 rows...
  Progress: 1000/1000 (100.0%)
✅ Successfully imported 1000 rows into table 'employee_sales'
```

### 6. SQL Interface
```
🔍 Interactive SQL Query Interface
✅ Command history and arrow keys enabled
Enter SQL queries or meta-commands:
  .tables     - List all tables
  .schema <table> - Show table structure  
  .exit/.quit - Exit
--------------------------------------------------
sql> .tables

Tables:
  sales

sql> SELECT employee_name, salary FROM sales WHERE salary > 60000 LIMIT 5;

employee_name        | salary              
---------------------|--------------------
Jane                 | 75000.5            
Alice                | 85000.0            
Charlie              | 65000.0            

(3 rows)

sql> .exit
Goodbye!
```

## Header Detection & Manual Entry

### Automatic Header Detection
The tool automatically detects if the first line contains headers or data, but **always asks for confirmation**:

```
🔍 Header Detection
==================================================
Detected first line as headers:
  1. employee_name
  2. age  
  3. department
  4. salary

First data row:
  1. John Smith
  2. 25
  3. Engineering
  4. 75000
==================================================

Are these correct field names? (y/n): 
```

### Manual Field Name Entry
When headers are not detected or user confirms first line is data:

```
🔍 No headers detected in TEXT file
First row appears to be data:
  1. John
  2. 25
  3. NYC
  4. 50000

📝 Manual Field Names Entry
Please enter 4 field names:
  Field 1 name: name
  Field 2 name: age
  Field 3 name: city
  Field 4 name: salary
```

### Graceful Interruption
- **Ctrl-C** during any prompt: Exits cleanly with "Operation cancelled by user"
- **No stack traces**: Clean exit without Python error messages
- **SQL Interface**: Ctrl-C exits to command line gracefully

## Table Name Configuration

The tool provides interactive table name confirmation for every import:

### Default Behavior
- **Filename-based**: Uses filename without extension as default (e.g., `sales.csv` → `sales`)
- **Command-line override**: `--table` argument sets the default
- **Interactive confirmation**: Always prompts for confirmation/modification

### Table Name Prompt
```
📋 Table Name Configuration
Source file: employee_data.csv
==================================================
Table name [employee_data]: employees

✅ Using table name: employees
```

### Validation Rules
- **Required**: Table name cannot be empty
- **Valid characters**: Must start with letter/underscore, contain only letters, numbers, underscores
- **Reserved words**: Prevents use of SQL keywords (table, select, insert, etc.)
- **Examples**:
  - ✅ `employees`, `sales_2024`, `_temp_data`
  - ❌ `select`, `123data`, `my-table`

### Multiple Files
When loading multiple files, each gets its own table name prompt:
```bash
python3 dbload.py sales.csv products.json --db company.db

# Prompts for:
# 1. Table name for sales.csv [sales]: 
# 2. Table name for products.json [products]:
```

## Enhanced SQL Interface

The interactive SQL interface includes modern command-line features:

### Command History & Navigation
- **↑/↓ Arrow Keys**: Navigate through command history
- **←/→ Arrow Keys**: Move cursor within current line for editing
- **Home/End**: Jump to beginning/end of line
- **Persistent History**: Commands saved to `~/.dbload_history` across sessions

### Tab Completion
- **SQL Keywords**: Auto-complete SELECT, FROM, WHERE, JOIN, etc.
- **Table Names**: Tab-complete existing table names in your database
- **Case Insensitive**: Works with both uppercase and lowercase

### Line Editing
- **Backspace/Delete**: Edit commands naturally
- **Ctrl-A/Ctrl-E**: Jump to start/end of line (Unix-style)
- **Ctrl-K/Ctrl-U**: Delete to end/start of line

### Example Session
```
sql> SEL[TAB] → SELECT
sql> SELECT * FROM emp[TAB] → SELECT * FROM employees
sql> [↑] → (recalls previous SELECT command)
sql> SELECT * FROM employees WHERE salary > 50000;
```

### Fallback Behavior
If readline is not available, the interface falls back to basic input with a warning:
```
⚠️  Install 'readline' for command history support
```

## Data Type Detection

The tool automatically detects appropriate SQLite data types:

- **INTEGER**: Whole numbers (`123`, `-456`)
- **REAL**: Decimal numbers (`123.45`, `3.14159`)  
- **TEXT**: Everything else (strings, mixed content)

**Detection Logic**:
- If 80%+ of values are integers → `INTEGER`
- If 80%+ of values are numeric (including decimals) → `REAL`  
- Otherwise → `TEXT`

## Error Handling

The tool gracefully handles common issues:

- **Missing Values**: Stored as `NULL` in database
- **Type Mismatches**: Falls back to `TEXT` storage
- **Malformed Files**: Clear error messages with suggestions
- **Large Files**: Progress indicators and batch processing
- **Invalid Characters**: Automatic sanitization of table/column names

## Meta-Commands

In the SQL interface:

| Command | Description |
|---------|-------------|
| `.tables` | List all tables in database |
| `.schema <table>` | Show structure of specific table |
| `.exit` or `.quit` | Exit the tool |

## Examples

### Example 1: CSV with Headers
```csv
name,age,city,salary
John,25,NYC,50000
Jane,30,LA,75000
Bob,35,Chicago,60000
```

### Example 2: JSON Array
```json
[
  {"name": "John", "age": 25, "city": "NYC", "salary": 50000},
  {"name": "Jane", "age": 30, "city": "LA", "salary": 75000}
]
```

### Example 3: Newline-Delimited JSON
```json
{"name": "John", "age": 25, "city": "NYC"}
{"name": "Jane", "age": 30, "city": "LA"}
```

### Example 4: Tab-Separated Text
```
name	age	city	salary
John	25	NYC	50000
Jane	30	LA	75000
```

## Tips

1. **Large Files**: The tool shows progress for files with 1000+ rows
2. **Schema Editing**: Use the `edit` option to customize field names and types
3. **Multiple Files**: Load related data into the same database for easy joins
4. **Query Results**: Results are limited to 100 rows for readability
5. **Database Reuse**: Specify the same `--db` name to add tables to existing databases

## Requirements

- Python 3.8+
- Standard library only (no external dependencies)
- SQLite support (included with Python)

## Error Recovery

If something goes wrong:

- **File not found**: Check file path and permissions
- **Parse errors**: Try specifying format manually or check file encoding
- **Database errors**: Ensure write permissions in current directory
- **Memory issues**: Tool processes large files in batches automatically
