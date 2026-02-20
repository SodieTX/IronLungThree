"""Dictation bar - Persistent text input at bottom of every tab.

The dictation bar is Anne's interface. Jeff types (or dictates),
Anne responds in the area above.

Phase 4.1: Text input with response display
Phase 4.10: Manual mode toggle for offline
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


class DictationBar(tk.Frame):
    """Persistent input bar at bottom of the application.

    Contains:
    - Response area (scrollable text showing Anne's output)
    - Text entry field (large, clear font, submit on Enter)
    - Manual mode indicator when offline
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_submit: Callable[[str], None],
        placeholder: str = "Speak or type...",
    ):
        """Initialize dictation bar.

        Args:
            parent: Parent widget
            on_submit: Callback when user submits input
            placeholder: Placeholder text for input field
        """
        super().__init__(parent)
        self._on_submit = on_submit
        self._placeholder = placeholder
        self._manual_mode = False
        self._has_placeholder = True

        self._create_widgets()
        self._bind_keys()

    def _create_widgets(self) -> None:
        """Create the dictation bar UI."""
        # Response area (Anne's output) — scrollable
        self._response_frame = tk.Frame(self)

        self._response_text = tk.Text(
            self._response_frame,
            height=4,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("TkDefaultFont", 11),
            bg="#f8f8f8",
            relief=tk.FLAT,
            padx=8,
            pady=4,
        )
        self._response_scrollbar = ttk.Scrollbar(
            self._response_frame,
            orient=tk.VERTICAL,
            command=self._response_text.yview,
        )
        self._response_text.configure(yscrollcommand=self._response_scrollbar.set)
        self._response_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._response_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Response area hidden initially
        # (packed on demand when show_response is called)

        # Input area
        self._input_frame = tk.Frame(self)
        self._input_frame.pack(fill=tk.X, padx=8, pady=4)

        # Manual mode indicator
        self._mode_label = ttk.Label(
            self._input_frame,
            text="",
            foreground="gray",
        )
        self._mode_label.pack(side=tk.LEFT, padx=(0, 4))

        # Text entry
        self._entry = tk.Entry(
            self._input_frame,
            font=("TkDefaultFont", 13),
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        # Show placeholder
        self._show_placeholder()

        # Submit button
        self._submit_btn = ttk.Button(
            self._input_frame,
            text="Send",
            command=self._handle_submit,
            width=8,
        )
        self._submit_btn.pack(side=tk.RIGHT)

    def _bind_keys(self) -> None:
        """Bind keyboard shortcuts."""
        self._entry.bind("<Return>", lambda e: self._handle_submit())
        self._entry.bind("<Escape>", lambda e: self.clear())
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

    def _show_placeholder(self) -> None:
        """Show placeholder text in entry."""
        self._entry.delete(0, tk.END)
        self._entry.insert(0, self._placeholder)
        self._entry.configure(foreground="gray")
        self._has_placeholder = True

    def _on_focus_in(self, event: object = None) -> None:
        """Clear placeholder on focus."""
        if self._has_placeholder:
            self._entry.delete(0, tk.END)
            self._entry.configure(foreground="black")
            self._has_placeholder = False

    def _on_focus_out(self, event: object = None) -> None:
        """Restore placeholder if empty."""
        if not self._entry.get().strip():
            self._show_placeholder()

    def _handle_submit(self) -> None:
        """Handle input submission."""
        if self._has_placeholder:
            return

        text = self._entry.get().strip()
        if not text:
            return

        self._entry.delete(0, tk.END)
        self._show_placeholder()

        if self._on_submit:
            self._on_submit(text)

    def get_input(self) -> str:
        """Get current input text."""
        if self._has_placeholder:
            return ""
        return self._entry.get().strip()

    def clear(self) -> None:
        """Clear input and response."""
        self._entry.delete(0, tk.END)
        self._show_placeholder()

    def show_response(self, text: str) -> None:
        """Show Anne's response above input."""
        # Show response area if hidden
        if not self._response_frame.winfo_ismapped():
            self._response_frame.pack(fill=tk.X, padx=8, pady=(4, 0), before=self._input_frame)

        self._response_text.configure(state=tk.NORMAL)
        self._response_text.delete("1.0", tk.END)
        self._response_text.insert("1.0", text)
        self._response_text.configure(state=tk.DISABLED)
        self._response_text.see(tk.END)

    def append_response(self, text: str) -> None:
        """Append to Anne's response area."""
        if not self._response_frame.winfo_ismapped():
            self._response_frame.pack(fill=tk.X, padx=8, pady=(4, 0), before=self._input_frame)

        self._response_text.configure(state=tk.NORMAL)
        self._response_text.insert(tk.END, "\n" + text)
        self._response_text.configure(state=tk.DISABLED)
        self._response_text.see(tk.END)

    def clear_response(self) -> None:
        """Clear the response area and hide it."""
        self._response_text.configure(state=tk.NORMAL)
        self._response_text.delete("1.0", tk.END)
        self._response_text.configure(state=tk.DISABLED)
        self._response_frame.pack_forget()

    def set_manual_mode(self, enabled: bool) -> None:
        """Enable manual mode (for offline)."""
        self._manual_mode = enabled
        if enabled:
            self._mode_label.configure(text="[MANUAL]", foreground="orange")
        else:
            self._mode_label.configure(text="", foreground="gray")

    def focus_input(self) -> None:
        """Focus the input entry."""
        self._on_focus_in()
        self._entry.focus_set()

    @property
    def is_manual_mode(self) -> bool:
        """Whether we're in manual (offline) mode."""
        return self._manual_mode
