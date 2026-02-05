"""Email template system using Jinja2.

Template types:
    - intro: First contact
    - follow_up: General follow-up
    - demo_confirmation: Demo scheduled confirmation
    - demo_invite: Demo invitation with Teams link
    - nurture_1/2/3: Warm Touch sequence
    - breakup: Final attempt

Usage:
    from src.engine.templates import render_template, list_templates

    html = render_template("intro", prospect=p, company=c, sender=s)
"""

from pathlib import Path
from typing import Any

try:
    import jinja2
except ImportError:
    jinja2 = None  # type: ignore[assignment]

from src.core.logging import get_logger
from src.db.models import Company, Prospect

logger = get_logger(__name__)


# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "emails"

# Default subject lines per template
_DEFAULT_SUBJECTS: dict[str, str] = {
    "intro": "Quick intro — {sender_company} + {company_name}",
    "follow_up": "Following up — {sender_company}",
    "demo_confirmation": "Demo confirmed — {demo_date}",
    "demo_invite": "Demo invite — {company_name} + {sender_company}",
    "nurture_1": "Quick thought for {company_name}",
    "nurture_2": "One more thing, {first_name}",
    "nurture_3": "Last note from me, {first_name}",
    "breakup": "Closing the loop — {company_name}",
}

# Jinja2 environment (created once, reused)
_env: object | None = None


def _get_env():
    """Get or create the Jinja2 environment."""
    if jinja2 is None:
        raise RuntimeError("jinja2 package not installed. Install with: pip install jinja2")
    global _env
    if _env is None:
        _env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
            autoescape=True,
            undefined=jinja2.Undefined,
        )
    return _env


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
        **kwargs: Additional template variables (sender, demo, etc.)

    Returns:
        Rendered HTML email body

    Raises:
        RuntimeError: If jinja2 is not installed
        jinja2.TemplateNotFound: If template does not exist
    """
    env = _get_env()
    template = env.get_template(f"{template_name}.html.j2")

    context = {
        "prospect": prospect,
        "company": company,
        **kwargs,
    }

    rendered: str = template.render(**context)
    logger.info(
        f"Rendered template: {template_name}",
        extra={"context": {"template": template_name}},
    )
    return rendered


def get_template_subject(
    template_name: str,
    prospect: Prospect,
    company: Company | None = None,
    **kwargs: Any,
) -> str:
    """Get subject line for a template.

    Uses default subject patterns with variable substitution.

    Args:
        template_name: Template name
        prospect: Prospect for personalization
        company: Company for personalization
        **kwargs: Additional variables (sender, demo, etc.)

    Returns:
        Subject line with variables filled in
    """
    pattern = _DEFAULT_SUBJECTS.get(template_name, template_name.replace("_", " ").title())

    sender = kwargs.get("sender", {})
    demo = kwargs.get("demo", {})

    # Build substitution dict
    subs = {
        "first_name": prospect.first_name or "",
        "last_name": prospect.last_name or "",
        "company_name": company.name if company else "",
        "sender_company": (
            sender.get("company", "")
            if isinstance(sender, dict)
            else getattr(sender, "company", "")
        ),
        "demo_date": "",
    }

    # Handle demo date formatting
    demo_date = demo.get("date") if isinstance(demo, dict) else getattr(demo, "date", None)
    if demo_date and hasattr(demo_date, "strftime"):
        subs["demo_date"] = demo_date.strftime("%A, %B %d")

    try:
        return pattern.format(**subs)
    except KeyError:
        return pattern


def list_templates() -> list[str]:
    """List available template names.

    Returns:
        Sorted list of template names (without .html.j2 extension)
    """
    if not TEMPLATE_DIR.exists():
        return []

    templates = [p.name.replace(".html.j2", "") for p in TEMPLATE_DIR.glob("*.html.j2")]
    return sorted(templates)


def validate_template(template_name: str) -> list[str]:
    """Validate a template.

    Checks:
        - Template file exists
        - Template parses without errors

    Args:
        template_name: Template name (without extension)

    Returns:
        List of issues (empty if valid)
    """
    issues: list[str] = []

    template_file = TEMPLATE_DIR / f"{template_name}.html.j2"
    if not template_file.exists():
        issues.append(f"Template file not found: {template_file}")
        return issues

    try:
        env = _get_env()
        env.get_template(f"{template_name}.html.j2")
    except jinja2.TemplateSyntaxError as e:
        issues.append(f"Template syntax error: {e}")

    return issues
