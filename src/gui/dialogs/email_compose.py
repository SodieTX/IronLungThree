"""Email compose dialog for sending emails from prospect cards.

Supports:
    - Template-based emails
    - Custom (freestyle) emails
    - Preview before sending
    - Draft mode (save without sending)
"""

import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import Company, ContactMethodType, Prospect
from src.gui.theme import COLORS, FONTS

logger = get_logger(__name__)


class EmailComposeDialog:
    """Email compose dialog for one-off emails from cards."""

    def __init__(
        self,
        parent: tk.Widget,
        prospect: Prospect,
        company: Optional[Company],
        db: Database,
        outlook: Optional[Any] = None,
    ):
        self.parent = parent
        self.prospect = prospect
        self.company = company or Company(name="Unknown", name_normalized="unknown")
        self.db = db
        self.outlook = outlook
        self._dialog: Optional[tk.Toplevel] = None
        self._mode_var = tk.StringVar(value="template")
        self._template_var = tk.StringVar()
        self._subject_var = tk.StringVar()
        self._instruction_var = tk.StringVar()
        self._body_text: Optional[tk.Text] = None
        self._template_frame: Optional[ttk.Frame] = None
        self._ai_frame: Optional[ttk.Frame] = None
        self._sent = False

    def show(self) -> bool:
        """Display the compose dialog. Returns True if email was sent/drafted."""
        self._dialog = tk.Toplevel(self.parent)
        self._dialog.title(f"Email — {self.prospect.full_name}")
        self._dialog.geometry("640x560")
        self._dialog.transient(self.parent.winfo_toplevel())
        self._dialog.grab_set()

        main = ttk.Frame(self._dialog, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        # Mode toggle: template vs custom
        mode_frame = ttk.Frame(main)
        mode_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Radiobutton(
            mode_frame,
            text="From Template",
            variable=self._mode_var,
            value="template",
            command=self._on_mode_change,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(
            mode_frame,
            text="Custom Email",
            variable=self._mode_var,
            value="custom",
            command=self._on_mode_change,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Radiobutton(
            mode_frame,
            text="Anne, write this",
            variable=self._mode_var,
            value="ai",
            command=self._on_mode_change,
        ).pack(side=tk.LEFT, padx=4)

        # Template selector
        self._template_frame = ttk.Frame(main)
        self._template_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(self._template_frame, text="Template:").pack(side=tk.LEFT, padx=(0, 4))

        templates = self._get_templates()
        ttk.Combobox(
            self._template_frame,
            textvariable=self._template_var,
            values=templates,
            state="readonly",
            width=30,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Button(self._template_frame, text="Preview", command=self._preview_template).pack(
            side=tk.LEFT, padx=4
        )

        # AI instruction frame (hidden by default)
        self._ai_frame = ttk.Frame(main)
        ttk.Label(self._ai_frame, text="Tell Anne what to write:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(self._ai_frame, textvariable=self._instruction_var, width=40).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4
        )
        ttk.Button(self._ai_frame, text="Generate", command=self._generate_ai_email).pack(
            side=tk.LEFT, padx=4
        )

        # Subject line
        subject_frame = ttk.Frame(main)
        subject_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(subject_frame, text="Subject:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Entry(subject_frame, textvariable=self._subject_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # Body area
        self._body_text = tk.Text(
            main,
            wrap=tk.WORD,
            font=FONTS["default"],
            height=16,
            bg=COLORS["bg_alt"],
            fg=COLORS["fg"],
            padx=8,
            pady=8,
        )
        self._body_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Recipient info
        recipient = self._get_recipient_email()
        recipient_text = f"To: {recipient}" if recipient else "To: (no email on file)"
        tk.Label(
            main,
            text=recipient_text,
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["muted"],
        ).pack(anchor="w")

        # Buttons
        btn_frame = ttk.Frame(main)
        btn_frame.pack(pady=(8, 0))
        ttk.Button(btn_frame, text="Send", command=self._on_send).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Save Draft", command=self._on_draft).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT, padx=4)

        self._dialog.bind("<Escape>", lambda e: self._on_cancel())

        self._dialog.wait_window()
        return self._sent

    def _on_mode_change(self) -> None:
        """Handle mode toggle between template, custom, and AI."""
        if not self._template_frame or not self._ai_frame:
            return
        mode = self._mode_var.get()
        if mode == "template":
            self._template_frame.pack(fill=tk.X, pady=(0, 8))
            self._ai_frame.pack_forget()
        elif mode == "ai":
            self._template_frame.pack_forget()
            self._ai_frame.pack(fill=tk.X, pady=(0, 8))
        else:
            self._template_frame.pack_forget()
            self._ai_frame.pack_forget()

    def _get_templates(self) -> list[str]:
        """Get available email template names."""
        try:
            from src.engine.templates import list_templates

            return list_templates()
        except Exception:
            return []

    def _get_recipient_email(self) -> Optional[str]:
        """Get the prospect's primary email."""
        if not self.prospect.id:
            return None
        methods = self.db.get_contact_methods(self.prospect.id)
        for m in methods:
            if m.type == ContactMethodType.EMAIL:
                return m.value
        return None

    def _preview_template(self) -> None:
        """Render and preview selected template."""
        template_name = self._template_var.get()
        if not template_name or not self._body_text:
            return

        try:
            from src.engine.templates import get_template_subject, render_template

            sender = {"name": "Jeff", "title": "", "company": "Nexys", "phone": ""}

            html = render_template(template_name, self.prospect, self.company, sender=sender)
            subject = get_template_subject(
                template_name, self.prospect, self.company, sender=sender
            )

            self._subject_var.set(subject)
            self._body_text.delete("1.0", tk.END)
            # Strip HTML tags for plain text preview
            text = re.sub(r"<[^>]+>", "", html)
            text = re.sub(r"\n{3,}", "\n\n", text)
            self._body_text.insert("1.0", text.strip())

        except Exception as e:
            logger.error(f"Template preview failed: {e}")
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showerror("Error", f"Template error: {e}", parent=parent)

    def _generate_ai_email(self) -> None:
        """Use AI to generate an email based on instruction."""
        instruction = self._instruction_var.get().strip()
        if not instruction or not self._body_text:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning(
                "Tell Anne",
                'Describe what you want, e.g. "short follow-up on our demo" '
                'or "intro email mentioning their growth".',
                parent=parent,
            )
            return

        try:
            from src.engine.email_gen import EmailGenerator

            generator = EmailGenerator(self.db)
            result = generator.generate_email(
                prospect=self.prospect,
                company=self.company,
                instruction=instruction,
            )

            self._subject_var.set(result.subject)
            self._body_text.delete("1.0", tk.END)
            self._body_text.insert("1.0", result.body)

            logger.info(
                f"AI email generated for {self.prospect.full_name}",
                extra={"context": {"tokens": result.tokens_used}},
            )

        except Exception as e:
            logger.error(f"AI email generation failed: {e}")
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showerror(
                "AI Unavailable",
                f"Anne couldn't generate this email: {e}\n\n"
                "Check your CLAUDE_API_KEY or switch to template/custom mode.",
                parent=parent,
            )

    def _on_send(self) -> None:
        """Send the email."""
        self._send_or_draft(draft_only=False)

    def _on_draft(self) -> None:
        """Save as draft."""
        self._send_or_draft(draft_only=True)

    def _send_or_draft(self, draft_only: bool = False) -> None:
        """Send or draft the email using EmailService."""
        if not self._body_text or not self.prospect.id:
            return

        subject = self._subject_var.get().strip()
        body = self._body_text.get("1.0", tk.END).strip()

        if not subject:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning("Missing Subject", "Enter a subject.", parent=parent)
            return
        if not body:
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showwarning("Missing Body", "Enter email body.", parent=parent)
            return

        try:
            from src.engine.email_service import EmailService

            service = EmailService(self.db, self.outlook)

            if self._mode_var.get() == "template" and self._template_var.get():
                sender = {
                    "name": "Jeff",
                    "title": "",
                    "company": "Nexys",
                    "phone": "",
                }
                result = service.send_from_template(
                    prospect_id=self.prospect.id,
                    template_name=self._template_var.get(),
                    sender=sender,
                    draft_only=draft_only,
                )
            else:
                result = service.send_custom(
                    prospect_id=self.prospect.id,
                    subject=subject,
                    body=body,
                    draft_only=draft_only,
                )

            if result.success:
                action = "drafted" if draft_only else "sent"
                logger.info(f"Email {action} to {self.prospect.full_name}")
                self._sent = True
                if self._dialog:
                    self._dialog.destroy()
            else:
                parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
                messagebox.showerror(
                    "Send Failed",
                    "Failed to send email. Check Outlook connection.",
                    parent=parent,
                )

        except Exception as e:
            logger.error(f"Email send failed: {e}", exc_info=True)
            parent = self._dialog if self._dialog else self.parent.winfo_toplevel()
            messagebox.showerror(
                "Error",
                f"Failed to send email: {type(e).__name__}. Check logs for details.",
                parent=parent,
            )

    def _on_cancel(self) -> None:
        """Cancel dialog."""
        if self._dialog:
            self._dialog.destroy()
