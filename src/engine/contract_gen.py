"""Nexys contract generator — template-based, no AI improvisation.

Renders contracts from Jinja2 templates using prospect/company/deal data.
Jeff can edit the template file as the contract evolves.

Usage:
    from src.engine.contract_gen import render_contract, list_contract_templates

    contract = render_contract(db, prospect_id)
    print(contract.content)
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

try:
    import jinja2
except ImportError:
    jinja2 = None  # type: ignore[assignment]

from src.core.logging import get_logger
from src.db.database import Database

logger = get_logger(__name__)


# Contract template directory
CONTRACT_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "contracts"

# Default commission rate (matches closed_won.py)
DEFAULT_COMMISSION_RATE = Decimal("0.06")


@dataclass
class GeneratedContract:
    """A rendered contract document.

    Attributes:
        template_name: Which template was used
        content: Rendered contract text
        prospect_id: Prospect this contract is for
        prospect_name: Prospect full name
        company_name: Company name
        deal_value: Deal value
        generated_at: When the contract was generated
    """

    template_name: str
    content: str
    prospect_id: int
    prospect_name: str
    company_name: str
    deal_value: Optional[Decimal] = None
    generated_at: str = ""

    def __post_init__(self) -> None:
        if not self.generated_at:
            self.generated_at = datetime.now().isoformat()


# Jinja2 environment for contracts (separate from email templates)
_env: object | None = None


def _get_env():
    """Get or create the Jinja2 environment for contracts."""
    if jinja2 is None:
        raise RuntimeError("jinja2 package not installed. Install with: pip install jinja2")
    global _env
    if _env is None:
        CONTRACT_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        _env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(CONTRACT_TEMPLATE_DIR)),
            autoescape=False,  # Plain text contracts, not HTML
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
        )
    return _env


def reset_env() -> None:
    """Reset the Jinja2 environment (for testing)."""
    global _env
    _env = None


def render_contract(
    db: Database,
    prospect_id: int,
    template_name: str = "nexys_standard",
    commission_rate: Optional[Decimal] = None,
) -> GeneratedContract:
    """Render a contract from a template using prospect/deal data.

    All data is pulled from the database. No AI generation — pure
    template substitution.

    Args:
        db: Database instance
        prospect_id: Prospect to generate contract for
        template_name: Template name (without .txt.j2 extension)
        commission_rate: Override commission rate (default 6%)

    Returns:
        GeneratedContract with rendered content

    Raises:
        ValueError: If prospect not found or missing deal data
        RuntimeError: If jinja2 not installed
        jinja2.TemplateNotFound: If template doesn't exist
    """
    prospect = db.get_prospect(prospect_id)
    if not prospect:
        raise ValueError(f"Prospect {prospect_id} not found")

    company = db.get_company(prospect.company_id)
    company_name = company.name if company else "Unknown"

    # Build template context — all fixed data, no AI
    rate = commission_rate or DEFAULT_COMMISSION_RATE
    raw_value = prospect.deal_value or 0
    deal_value = Decimal(str(raw_value))
    commission = deal_value * rate
    close_date = prospect.close_date or date.today()

    context = {
        # Prospect
        "prospect_name": prospect.full_name,
        "prospect_first_name": prospect.first_name,
        "prospect_last_name": prospect.last_name,
        "prospect_title": prospect.title or "",
        # Company
        "company_name": company_name,
        "company_domain": company.domain if company else "",
        "company_state": company.state if company else "",
        "company_size": company.size if company else "",
        "loan_types": company.loan_types if company else "",
        # Deal
        "deal_value": f"{deal_value:,.2f}",
        "deal_value_raw": deal_value,
        "close_date": close_date.isoformat(),
        "close_date_formatted": close_date.strftime("%B %d, %Y"),
        "close_notes": prospect.close_notes or "",
        "commission": f"{commission:,.2f}",
        "commission_rate": f"{rate * 100:.0f}",
        # Meta
        "today": date.today().strftime("%B %d, %Y"),
        "today_iso": date.today().isoformat(),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    env = _get_env()
    template = env.get_template(f"{template_name}.txt.j2")
    content: str = template.render(**context)

    logger.info(
        "Contract generated",
        extra={
            "context": {
                "template": template_name,
                "prospect_id": prospect_id,
                "company": company_name,
            }
        },
    )

    return GeneratedContract(
        template_name=template_name,
        content=content,
        prospect_id=prospect_id,
        prospect_name=prospect.full_name,
        company_name=company_name,
        deal_value=deal_value,
    )


def list_contract_templates() -> list[str]:
    """List available contract template names.

    Returns:
        Sorted list of template names (without .txt.j2 extension)
    """
    if not CONTRACT_TEMPLATE_DIR.exists():
        return []

    templates = [p.name.replace(".txt.j2", "") for p in CONTRACT_TEMPLATE_DIR.glob("*.txt.j2")]
    return sorted(templates)


def get_template_path(template_name: str) -> Path:
    """Get the filesystem path for a contract template.

    Useful for opening the template in an editor.

    Args:
        template_name: Template name (without extension)

    Returns:
        Path to the template file

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    path = CONTRACT_TEMPLATE_DIR / f"{template_name}.txt.j2"
    if not path.exists():
        raise FileNotFoundError(f"Contract template not found: {path}")
    return path
