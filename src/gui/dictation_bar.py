"""Dictation bar - Persistent input at bottom of every tab."""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from src.core.logging import get_logger
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class DictationBar(tk.Frame):
    """Persistent text input widget.

    Sits at the bottom of the main window. Accepts free-text input
    and sends it to the on_submit callback (typically Anne / AI copilot).
    Shows AI responses in a label above the input.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_submit: Callable[[str], None],
        placeholder: str = "Speak or type...",
    ):
        super().__init__(parent, bg=COLORS["bg_alt"], bd=1, relief=tk.GROOVE)
        self._on_submit = on_submit
        self._placeholder = placeholder
        self._manual_mode = False

        # Response area (hidden until show_response is called)
        self._response_frame = tk.Frame(self, bg=COLORS["bg_alt"])
        self._response_label = tk.Label(
            self._response_frame,
            text="",
            font=FONTS["default"],
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
            wraplength=700,
            justify=tk.LEFT,
            anchor=tk.W,
        )
        self._response_label.pack(fill=tk.X, padx=10, pady=(6, 2))

        # Input row
        input_frame = tk.Frame(self, bg=COLORS["bg_alt"])
        input_frame.pack(fill=tk.X, padx=8, pady=6)

        self._mode_label = ttk.Label(input_frame, text="Anne", style="Accent.TLabel")
        self._mode_label.pack(side=tk.LEFT, padx=(0, 8))

        self._entry = ttk.Entry(input_frame, font=FONTS["default"])
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self._submit_btn = ttk.Button(
            input_frame, text="Send", style="Accent.TButton", command=self._handle_submit
        )
        self._submit_btn.pack(side=tk.RIGHT)

        # Placeholder behaviour
        self._has_placeholder = True
        self._set_placeholder()
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)
        self._entry.bind("<Return>", lambda e: self._handle_submit())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_input(self) -> str:
        """Get current input text (empty string if only placeholder)."""
        if self._has_placeholder:
            return ""
        return self._entry.get().strip()

    def clear(self) -> None:
        """Clear input and re-show placeholder."""
        self._entry.delete(0, tk.END)
        self._set_placeholder()

    def show_response(self, text: str) -> None:
        """Show Anne's response above the input field."""
        self._response_label.configure(text=text)
        self._response_frame.pack(fill=tk.X, before=self._entry.master)

    def hide_response(self) -> None:
        """Hide the response area."""
        self._response_frame.pack_forget()

    def set_manual_mode(self, enabled: bool) -> None:
        """Enable manual mode (for offline — labels the bar differently)."""
        self._manual_mode = enabled
        if enabled:
            self._mode_label.configure(text="Manual")
        else:
            self._mode_label.configure(text="Anne")

    def focus_input(self) -> None:
        """Move focus to the input entry."""
        self._entry.focus_set()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _handle_submit(self) -> None:
        """Submit current input."""
        text = self.get_input()
        if not text:
            return
        logger.debug("Dictation submitted", extra={"context": {"length": len(text)}})
        self.clear()
        self._on_submit(text)

    def _set_placeholder(self) -> None:
        self._entry.delete(0, tk.END)
        self._entry.insert(0, self._placeholder)
        self._entry.configure(foreground=COLORS["muted"])
        self._has_placeholder = True

    def _on_focus_in(self, event: tk.Event = None) -> None:  # type: ignore[assignment]
        if self._has_placeholder:
            self._entry.delete(0, tk.END)
            self._entry.configure(foreground=COLORS["fg"])
            self._has_placeholder = False

    def _on_focus_out(self, event: tk.Event = None) -> None:  # type: ignore[assignment]
        if not self._entry.get().strip():
            self._set_placeholder()
