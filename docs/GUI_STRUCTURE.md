# IronLung 3 GUI Structure

## Application Layout

```
┌──────────────────────────────────────────────────┐
│ IronLung 3                              [_][□][X]│
├──────────────────────────────────────────────────┤
│ ┏━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┓                   │
│ ┃ Import┃ Pipeline┃ Settings┃                   │
│ ┗━━━━━━━┻━━━━━━━━━┻━━━━━━━━━┛                   │
│                                                  │
│              TAB CONTENT AREA                    │
│                                                  │
├──────────────────────────────────────────────────┤
│ 245 prospects | 150 unengaged | 42 engaged       │
└──────────────────────────────────────────────────┘
```

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
