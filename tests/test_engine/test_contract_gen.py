"""Tests for Nexys contract generator."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.db.models import Company, Population, Prospect
from src.engine.contract_gen import (
    CONTRACT_TEMPLATE_DIR,
    GeneratedContract,
    get_template_path,
    list_contract_templates,
    render_contract,
    reset_env,
)


@pytest.fixture(autouse=True)
def clean_env():
    """Reset Jinja2 env between tests."""
    reset_env()
    yield
    reset_env()


@pytest.fixture
def contract_template_dir(tmp_path):
    """Create a temp contract template directory with a test template."""
    template_dir = tmp_path / "templates" / "contracts"
    template_dir.mkdir(parents=True)

    template_content = """\
CONTRACT FOR {{ company_name }}
Contact: {{ prospect_name }}
Title: {{ prospect_title }}
Deal: ${{ deal_value }}
Close Date: {{ close_date_formatted }}
Commission: ${{ commission }} ({{ commission_rate }}%)
State: {{ company_state }}
Loan Types: {{ loan_types }}
Notes: {{ close_notes }}
Today: {{ today }}
"""
    (template_dir / "nexys_standard.txt.j2").write_text(template_content)
    return template_dir


@pytest.fixture
def closed_prospect(memory_db):
    """Create a closed-won prospect with deal data in the DB."""
    company = Company(
        name="ABC Lending",
        name_normalized="abc lending",
        domain="abclending.com",
        state="TX",
        loan_types="Bridge, Fix-and-Flip",
        size="medium",
        timezone="central",
    )
    company_id = memory_db.create_company(company)

    prospect = Prospect(
        company_id=company_id,
        first_name="John",
        last_name="Smith",
        title="CEO",
        population=Population.CLOSED_WON,
        prospect_score=85,
        data_confidence=90,
        deal_value=5000.00,
        close_date=date(2026, 2, 15),
        close_notes="12-month contract, 200 users, starts March 1",
    )
    prospect_id = memory_db.create_prospect(prospect)
    return prospect_id


@pytest.fixture
def minimal_prospect(memory_db):
    """Create a closed prospect with minimal data (no title, no notes)."""
    company = Company(
        name="XYZ Corp",
        name_normalized="xyz",
    )
    company_id = memory_db.create_company(company)

    prospect = Prospect(
        company_id=company_id,
        first_name="Jane",
        last_name="Doe",
        population=Population.CLOSED_WON,
        deal_value=2500.00,
        close_date=date(2026, 3, 1),
    )
    prospect_id = memory_db.create_prospect(prospect)
    return prospect_id


class TestRenderContract:
    """Test contract rendering."""

    def test_render_full_data(self, memory_db, closed_prospect, contract_template_dir, monkeypatch):
        """Contract renders with all prospect data substituted."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        contract = render_contract(memory_db, closed_prospect)

        assert isinstance(contract, GeneratedContract)
        assert "ABC Lending" in contract.content
        assert "John Smith" in contract.content
        assert "CEO" in contract.content
        assert "5,000.00" in contract.content
        assert "February 15, 2026" in contract.content
        assert "300.00" in contract.content  # Commission: 5000 * 6%
        assert "6" in contract.content  # Commission rate
        assert "TX" in contract.content
        assert "Bridge, Fix-and-Flip" in contract.content
        assert "12-month contract" in contract.content

    def test_render_minimal_data(self, memory_db, minimal_prospect, contract_template_dir, monkeypatch):
        """Contract renders gracefully with missing optional fields."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        contract = render_contract(memory_db, minimal_prospect)

        assert "XYZ Corp" in contract.content
        assert "Jane Doe" in contract.content
        assert "2,500.00" in contract.content

    def test_render_returns_generated_contract(self, memory_db, closed_prospect, contract_template_dir, monkeypatch):
        """render_contract returns a proper GeneratedContract."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        contract = render_contract(memory_db, closed_prospect)

        assert contract.template_name == "nexys_standard"
        assert contract.prospect_id == closed_prospect
        assert contract.prospect_name == "John Smith"
        assert contract.company_name == "ABC Lending"
        assert float(contract.deal_value) == 5000.00
        assert contract.generated_at  # Has a timestamp

    def test_render_custom_commission_rate(self, memory_db, closed_prospect, contract_template_dir, monkeypatch):
        """Commission rate can be overridden."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        contract = render_contract(
            memory_db, closed_prospect, commission_rate=Decimal("0.08")
        )

        assert "400.00" in contract.content  # 5000 * 8%
        assert "8" in contract.content  # Rate

    def test_render_prospect_not_found(self, memory_db, contract_template_dir, monkeypatch):
        """ValueError raised for nonexistent prospect."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        with pytest.raises(ValueError, match="not found"):
            render_contract(memory_db, 99999)

    def test_render_template_not_found(self, memory_db, closed_prospect, contract_template_dir, monkeypatch):
        """TemplateNotFound raised for missing template."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        import jinja2

        with pytest.raises(jinja2.TemplateNotFound):
            render_contract(memory_db, closed_prospect, template_name="nonexistent")

    def test_render_no_deal_value_defaults_zero(self, memory_db, contract_template_dir, monkeypatch):
        """Prospect with no deal_value gets $0.00."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        company = Company(name="Test Co", name_normalized="test")
        company_id = memory_db.create_company(company)
        prospect = Prospect(
            company_id=company_id,
            first_name="Test",
            last_name="User",
            population=Population.CLOSED_WON,
        )
        prospect_id = memory_db.create_prospect(prospect)

        contract = render_contract(memory_db, prospect_id)
        assert "0.00" in contract.content


class TestListContractTemplates:
    """Test template listing."""

    def test_list_templates(self, contract_template_dir, monkeypatch):
        """Lists available templates."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        templates = list_contract_templates()
        assert "nexys_standard" in templates

    def test_list_templates_empty(self, tmp_path, monkeypatch):
        """Empty directory returns empty list."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", empty_dir
        )

        templates = list_contract_templates()
        assert templates == []

    def test_list_templates_nonexistent_dir(self, tmp_path, monkeypatch):
        """Nonexistent directory returns empty list."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR",
            tmp_path / "does_not_exist",
        )

        templates = list_contract_templates()
        assert templates == []

    def test_list_multiple_templates(self, contract_template_dir, monkeypatch):
        """Lists multiple templates sorted alphabetically."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        # Add a second template
        (contract_template_dir / "custom.txt.j2").write_text("Custom: {{ company_name }}")

        templates = list_contract_templates()
        assert templates == ["custom", "nexys_standard"]


class TestGetTemplatePath:
    """Test template path resolution."""

    def test_get_existing_template(self, contract_template_dir, monkeypatch):
        """Returns path for existing template."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        path = get_template_path("nexys_standard")
        assert path.exists()
        assert path.name == "nexys_standard.txt.j2"

    def test_get_nonexistent_template(self, contract_template_dir, monkeypatch):
        """FileNotFoundError for missing template."""
        monkeypatch.setattr(
            "src.engine.contract_gen.CONTRACT_TEMPLATE_DIR", contract_template_dir
        )

        with pytest.raises(FileNotFoundError, match="not found"):
            get_template_path("nonexistent")


class TestGeneratedContract:
    """Test GeneratedContract dataclass."""

    def test_generated_at_auto_set(self):
        """generated_at is auto-populated if not provided."""
        contract = GeneratedContract(
            template_name="test",
            content="content",
            prospect_id=1,
            prospect_name="Test",
            company_name="Co",
        )
        assert contract.generated_at  # Non-empty

    def test_generated_at_preserved(self):
        """Explicit generated_at is preserved."""
        contract = GeneratedContract(
            template_name="test",
            content="content",
            prospect_id=1,
            prospect_name="Test",
            company_name="Co",
            generated_at="2026-02-20T10:00:00",
        )
        assert contract.generated_at == "2026-02-20T10:00:00"


class TestNoAIUsage:
    """Verify contract generation uses no AI."""

    def test_no_claude_import(self):
        """contract_gen.py does not import any AI modules."""
        import importlib
        import inspect

        from src.engine import contract_gen

        source = inspect.getsource(contract_gen)
        assert "ClaudeClientMixin" not in source
        assert "anthropic" not in source
        assert "ai.anne" not in source
