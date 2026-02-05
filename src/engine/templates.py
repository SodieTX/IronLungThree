"""Email template system using Jinja2.

Template types:
    - intro: First contact
    - follow_up: General follow-up
    - demo_confirmation: Demo scheduled confirmation
    - demo_invite: Demo invitation with Teams link
    - nurture_1/2/3: Warm Touch sequence
    - breakup: Final attempt

Usage:
    from src.engine.templates import render_template

    html = render_template("intro", prospect=p, company=c)
"""

from pathlib import Path
from typing import Any, Optional

from src.core.logging import get_logger
from src.db.models import Company, Prospect

logger = get_logger(__name__)


# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "emails"


def render_template(
    template_name: str,
    prospect: Prospect,
    company: Company,
    **kwargs: Any,
) -> str:
    """Render email template with prospect data.

    Args:
        template_name: Template name (without extension)
        prospect: Prospect data
        company: Company data
        **kwargs: Additional template variables

    Returns:
        Rendered HTML email body
    """
    raise NotImplementedError("Phase 3, Step 3.4")


def get_template_subject(template_name: str, prospect: Prospect) -> str:
    """Get subject line for template.

    Reads from template frontmatter.

    Args:
        template_name: Template name
        prospect: Prospect for personalization

    Returns:
        Subject line
    """
    raise NotImplementedError("Phase 3, Step 3.4")


def list_templates() -> list[str]:
    """List available template names.

    Returns:
        List of template names
    """
    raise NotImplementedError("Phase 3, Step 3.4")


def validate_template(template_name: str) -> list[str]:
    """Validate a template.

    Checks:
        - Template exists
        - Frontmatter is valid
        - Required variables are documented

    Returns:
        List of issues (empty if valid)
    """
    raise NotImplementedError("Phase 3, Step 3.4")
