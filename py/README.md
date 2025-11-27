# Python Tools

This directory contains Python-based command-line tools.

## Tools

### [joinfiles](joinfiles/README.md)

SQL-like left join for text files based on field matching.

**Quick Usage:**
```bash
cd joinfiles
python3 joinfiles.py file1.txt file2.txt -k 1,2 -o result.txt
```

### [dbload](dbload/README.md)

Interactive database loader with auto-detection for CSV, JSON, and text files.

**Quick Usage:**
```bash
cd dbload
python3 dbload.py data.csv --db mydata.db
```

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
