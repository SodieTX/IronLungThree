# IronLung 3 GUI Manual Test Guide

## Prerequisites
- Python 3.11+ with tkinter installed
- IronLung 3 repository cloned
- Required dependencies installed

## Setup
```bash
pip install -r requirements.txt
python ironlung3.py
```

## Test Scenarios

### Test 1: Application Launch
1. Run `python ironlung3.py`
2. Verify window titled "IronLung 3" appears at 1200x800
3. Verify three tabs: Import, Pipeline, Settings
4. Verify status bar shows prospect counts

### Test 2: Import Tab - File Selection
1. Click Import tab → Select File
2. Navigate to `data/sample_contacts.csv`
3. Verify filename appears and column mappings show

### Test 3: Import Tab - Column Mapping
1. Review auto-mapped columns
2. Adjust any incorrect mappings via dropdowns

### Test 4: Import Tab - Preview
1. Click "Preview Import"
2. Verify summary counts and first 5 records display

### Test 5: Import Tab - Execute Import
1. Click "Execute Import" → Confirm
2. Verify success message with counts

### Test 6-9: Pipeline Tab
6. View all prospects in treeview
7. Filter by population dropdown
8. Search by name/title
9. Export view to CSV

### Test 10-13: Pipeline Actions
10. Double-click prospect for details
11. Bulk move selected prospects
12. Bulk park selected prospects
13. Sort by column headers

### Test 14-18: General
14. Ctrl+Q closes app
15. Status bar updates after changes
16. Settings tab opens without errors
17. Window close (X) works gracefully
18. Error handling for invalid operations
