# IronLung 3 GUI Manual Test Guide

## Prerequisites
- Python 3.11+ with tkinter installed
- IronLung 3 repository cloned
- Required dependencies installed

## Setup
```bash
# Install dependencies if not already done
pip install -r requirements.txt

# Optionally, seed demo data
python scripts/seed_demo_data.py
```

## Test 1: Application Launch

### Steps:
1. Run `python ironlung3.py`
2. Observe the main window

### Expected Results:
- ✓ Window titled "IronLung 3" appears
- ✓ Window size is 1200x800
- ✓ Three tabs visible: Import, Pipeline, Settings
- ✓ Status bar at bottom shows: "X prospects | Y unengaged | Z engaged"
- ✓ No errors in console

## Test 2: Import Tab - File Selection

### Steps:
1. Click on Import tab
2. Click "Select File" button
3. Navigate to `data/sample_contacts.csv`
4. Select the file

### Expected Results:
- ✓ File dialog opens
- ✓ Selected filename appears next to button
- ✓ Column mapping section appears
- ✓ Dropdown shows "None" or auto-detected preset
- ✓ Mapping dropdowns show CSV headers
- ✓ Some fields auto-mapped based on column names
- ✓ Preview and Import buttons become enabled

## Test 3: Import Tab - Column Mapping

### Steps:
1. After selecting a file, review the column mappings
2. Manually adjust any incorrect mappings using the dropdowns

### Expected Results:
- ✓ Each field (First Name, Last Name, Email, etc.) has a dropdown
- ✓ Dropdowns contain CSV column headers
- ✓ At least some fields are auto-mapped correctly
- ✓ Can change mappings via dropdowns

## Test 4: Import Tab - Preview Import

### Steps:
1. With file selected and columns mapped
2. Click "Preview Import" button

### Expected Results:
- ✓ Dialog opens showing import summary
- ✓ Shows counts: New prospects, Merges, Needs review, Blocked (DNC), Incomplete
- ✓ Shows first 5 records with details
- ✓ If any DNC blocks, they're highlighted in red
- ✓ Can close dialog

## Test 5: Import Tab - Execute Import

### Steps:
1. Click "Execute Import" button
2. Confirm in dialog

### Expected Results:
- ✓ Confirmation dialog appears
- ✓ After confirm, import processes
- ✓ Success message shows counts (Created, Merged, Blocked)
- ✓ Import history section updates
- ✓ File selection clears
- ✓ Status bar updates with new prospect count

## Test 6: Pipeline Tab - View Prospects

### Steps:
1. Click Pipeline tab
2. Observe the prospect list

### Expected Results:
- ✓ Treeview shows all prospects
- ✓ Columns: ID, Name, Population, Title, Score
- ✓ Data is visible and readable
- ✓ Can scroll if many prospects
- ✓ Status bar shows correct counts

## Test 7: Pipeline Tab - Filter by Population

### Steps:
1. In Pipeline tab
2. Click Population dropdown
3. Select "unengaged"

### Expected Results:
- ✓ Dropdown shows all population values
- ✓ List filters to show only unengaged prospects
- ✓ Other populations hidden

## Test 8: Pipeline Tab - Search

### Steps:
1. In Pipeline tab, ensure some prospects are visible
2. Type a name or part of name in Search box

### Expected Results:
- ✓ List filters as you type
- ✓ Only matching prospects shown
- ✓ Matches name, title, or population

## Test 9: Pipeline Tab - Export

### Steps:
1. In Pipeline tab
2. Click "Export View" button
3. Choose a save location

### Expected Results:
- ✓ File save dialog opens
- ✓ Default extension is .csv
- ✓ After save, success message appears
- ✓ CSV file contains current view data

## Test 10: Pipeline Tab - View Prospect Details

### Steps:
1. In Pipeline tab
2. Double-click a prospect row

### Expected Results:
- ✓ Details dialog opens
- ✓ Shows: ID, Name, Title, Population, Score
- ✓ Shows notes if any
- ✓ Shows company info if available
- ✓ Can close dialog

## Test 11: Pipeline Tab - Bulk Move

### Steps:
1. In Pipeline tab
2. Select multiple prospects (click first, shift-click last)
3. Choose population in "Move to:" dropdown
4. Click "Apply Move"
5. Confirm in dialog

### Expected Results:
- ✓ Can select multiple rows
- ✓ Selection count updates (e.g., "3 selected")
- ✓ Confirmation dialog appears
- ✓ After confirm, prospects move
- ✓ Success message shows
- ✓ List refreshes with new populations

## Test 12: Pipeline Tab - Bulk Park

### Steps:
1. Select multiple prospects
2. Choose a month in "Park in:" dropdown
3. Click "Apply Park"
4. Confirm in dialog

### Expected Results:
- ✓ Month dropdown shows future months (YYYY-MM format)
- ✓ Confirmation dialog appears
- ✓ After confirm, prospects marked as parked
- ✓ Success message shows
- ✓ List refreshes

## Test 13: Pipeline Tab - Sorting

### Steps:
1. Click on different column headers (ID, Name, etc.)

### Expected Results:
- ✓ List sorts by clicked column
- ✓ Numeric columns sort numerically
- ✓ Text columns sort alphabetically

## Test 14: Keyboard Shortcuts

### Steps:
1. With app open, press Ctrl+Q

### Expected Results:
- ✓ App closes gracefully
- ✓ No errors or crashes

Alternative: Try Ctrl+W - should also close

## Test 15: Status Bar Updates

### Steps:
1. Import prospects
2. Move some to different populations
3. Switch between tabs

### Expected Results:
- ✓ Status bar updates after imports
- ✓ Status bar updates after bulk moves
- ✓ Counts are accurate
- ✓ Format: "X prospects | Y unengaged | Z engaged"

## Test 16: Settings Tab

### Steps:
1. Click Settings tab

### Expected Results:
- ✓ Tab opens without errors
- ✓ Shows service readiness status (Phase 1 may be minimal)

## Test 17: Window Close

### Steps:
1. Click window close button (X)

### Expected Results:
- ✓ App closes gracefully
- ✓ No error messages
- ✓ No hanging processes

## Test 18: Error Handling

### Steps:
1. Try to import with no file selected
2. Try to export with no prospects
3. Try bulk actions with no selection

### Expected Results:
- ✓ Warning/error messages appear
- ✓ App doesn't crash
- ✓ Error messages are user-friendly

## Common Issues & Troubleshooting

### Issue: "No module named 'tkinter'"
**Solution:** Install tkinter for your OS:
- Ubuntu/Debian: `sudo apt-get install python3-tk`
- MacOS: Included with Python from python.org
- Windows: Included with Python installer

### Issue: Window doesn't appear
**Solution:** 
- Check for errors in console
- Ensure database initialized: Check `data/ironlung3.db` exists
- Try: `python -c "import tkinter; tkinter.Tk()"`

### Issue: Import fails
**Solution:**
- Verify CSV format is correct
- Check logs in console
- Ensure required columns are mapped

## Success Criteria

All tests should pass with:
- ✓ No crashes or uncaught exceptions
- ✓ UI is responsive and functional
- ✓ Data persists between sessions
- ✓ User-friendly error messages
- ✓ Clean application startup and shutdown

## Notes
- Phase 1 focuses on basic functionality
- Advanced features (card views, morning brief, etc.) are Phase 2+
- Settings tab is minimal in Phase 1
- Report any issues with details: steps to reproduce, error messages, environment
