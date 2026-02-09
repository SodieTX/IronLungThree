# IronLung 3 GUI Structure

## Application Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ IronLung 3                                                        [_][□][X]│
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────┐ │
│ │ ┏━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓                                     │ │
│ │ ┃ Import┃ Pipeline┃ Settings┃                                     │ │
│ │ ┗━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┛                                     │ │
│ │ ┌─────────────────────────────────────────────────────────────────┐ │ │
│ │ │                                                                 │ │ │
│ │ │                                                                 │ │ │
│ │ │                      TAB CONTENT AREA                          │ │ │
│ │ │                                                                 │ │ │
│ │ │                                                                 │ │ │
│ │ │                                                                 │ │ │
│ │ └─────────────────────────────────────────────────────────────────┘ │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│ 245 prospects | 150 unengaged | 42 engaged                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Import Tab Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ File Selection                                                          │
│ ┌─────────────┐ selected_file.csv                                      │
│ │ Select File │                                                         │
│ └─────────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Auto-detect preset: [PhoneBurner      ▼]                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Column Mapping                                                          │
│                                                                         │
│  First Name:    [First Name          ▼]                               │
│  Last Name:     [Last Name           ▼]                               │
│  Email:         [Email Address       ▼]                               │
│  Phone:         [Phone Number        ▼]                               │
│  Company:       [Company             ▼]                               │
│  Title:         [Title               ▼]                               │
│  State:         [State               ▼]                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────┐  ┌───────────────────┐
│  Preview Import     │  │  Execute Import   │
└─────────────────────┘  └───────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Import History                                                          │
│                                                                         │
│  2024-02-09 10:30 - Imported 25 prospects from contacts.csv           │
│  2024-02-08 14:15 - Imported 50 prospects from leads_feb.csv          │
│  2024-02-07 09:00 - Imported 15 prospects from referrals.csv          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Pipeline Tab Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Population: [All          ▼]  Search: [_________________]  [Export View]│
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ ID │ Name              │ Population   │ Title        │ Score │▲│        │
├────┼───────────────────┼──────────────┼──────────────┼───────┤││        │
│ 1  │ John Smith        │ unengaged    │ CEO          │ 85    │││        │
│ 2  │ Jane Doe          │ engaged      │ CFO          │ 92    │││        │
│ 3  │ Bob Johnson       │ unengaged    │ VP Sales     │ 78    │││        │
│ 4  │ Alice Williams    │ broken       │ Director     │ 65    │││        │
│ 5  │ Charlie Brown     │ engaged      │ Manager      │ 88    │││        │
│ ...│ ...               │ ...          │ ...          │ ...   │▼│        │
└─────────────────────────────────────────────────────────────────────────┘
                                                                 ◄────────►

┌─────────────────────────────────────────────────────────────────────────┐
│ Bulk Actions:                                                           │
│ Move to: [unengaged     ▼] [Apply Move]                               │
│ Park in: [2024-03       ▼] [Apply Park]                    3 selected  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Import Preview Dialog

```
┌───────────────────────────────────────────┐
│ Import Preview                      [X]   │
├───────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐   │
│ │ Summary                             │   │
│ │                                     │   │
│ │ New prospects: 23                   │   │
│ │ Will be merged: 2                   │   │
│ │ Needs review: 0                     │   │
│ │ Blocked (DNC): 1                    │   │
│ │ Incomplete: 3                       │   │
│ │                                     │   │
│ └─────────────────────────────────────┘   │
│ ┌─────────────────────────────────────┐   │
│ │ Details (First 5)                   │   │
│ │                                     │   │
│ │ 1. John Smith                       │   │
│ │    Company: Acme Corp               │   │
│ │    Email: john@acme.com             │   │
│ │                                     │   │
│ │ 2. Jane Doe                         │   │
│ │    Company: TechStart Inc           │   │
│ │    Email: jane@techstart.com        │   │
│ │                                     │   │
│ │ ⚠️ BLOCKED (DNC):                   │   │
│ │ 1. Spam User - spam@blocked.com     │   │
│ │                                     │   │
│ └─────────────────────────────────────┘   │
│                    ┌────────┐             │
│                    │ Close  │             │
│                    └────────┘             │
└───────────────────────────────────────────┘
```

## Prospect Details Dialog

```
┌───────────────────────────────────────────┐
│ Prospect Details - John Smith       [X]   │
├───────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐   │
│ │ ID: 1                               │   │
│ │ Name: John Smith                    │   │
│ │ Title: CEO                          │   │
│ │ Population: unengaged               │   │
│ │ Score: 85                           │   │
│ │                                     │   │
│ │ Notes:                              │   │
│ │ Met at conference. Interested in    │   │
│ │ our enterprise solution.            │   │
│ │                                     │   │
│ │ Company: Acme Corp                  │   │
│ │ State: TX                           │   │
│ │                                     │   │
│ └─────────────────────────────────────┘   │
│                    ┌────────┐             │
│                    │ Close  │             │
│                    └────────┘             │
└───────────────────────────────────────────┘
```

## Navigation Flow

```
┌─────────────┐
│  App Start  │
└──────┬──────┘
       │
       ▼
┌─────────────┐     User selects     ┌──────────────┐
│ Import Tab  │◄─────────────────────│ Pipeline Tab │
└──────┬──────┘         tab          └───────┬──────┘
       │                                     │
       ▼                                     ▼
┌─────────────┐                      ┌──────────────┐
│ Select File │                      │ View / Filter│
└──────┬──────┘                      └───────┬──────┘
       │                                     │
       ▼                                     ▼
┌─────────────┐                      ┌──────────────┐
│  Map Cols   │                      │ Double-Click │
└──────┬──────┘                      └───────┬──────┘
       │                                     │
       ▼                                     ▼
┌─────────────┐                      ┌──────────────┐
│   Preview   │                      │   Details    │
└──────┬──────┘                      └──────────────┘
       │
       ▼
┌─────────────┐
│   Import    │──────────┐
└─────────────┘          │
                         │
                         ▼
                  ┌──────────────┐
                  │Pipeline Tab  │
                  │(auto-refresh)│
                  └──────────────┘
```

## Keyboard Shortcuts

- **Ctrl+Q**: Close application
- **Ctrl+W**: Close application
- **Enter**: Submit focused action (e.g., confirm dialog)
- **Escape**: Cancel focused action (e.g., close dialog)
- **Arrow Keys**: Navigate treeview
- **Shift+Click**: Multi-select in treeview

## Color Coding

- **Normal Text**: Black (#333333)
- **Backgrounds**: Light gray (#f5f5f5) / White (#ffffff)
- **Accents**: Blue (#0066cc)
- **Success**: Green (#28a745)
- **Warning**: Orange (#ffc107)
- **Error/DNC**: Red (#dc3545)

## Widget Types Used

- **ttk.Frame**: Container widgets
- **ttk.Label**: Text labels
- **ttk.Button**: Action buttons
- **ttk.Combobox**: Dropdowns
- **ttk.Entry**: Text input
- **ttk.Treeview**: Table/list view
- **ttk.Scrollbar**: Scrolling
- **tk.Text**: Multi-line text display
- **tk.Canvas**: Scrollable containers
- **tk.Toplevel**: Modal dialogs
