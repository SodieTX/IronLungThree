"""Tests for email template rendering."""

from datetime import datetime

import pytest

from src.db.models import Company, Prospect
from src.engine.templates import (
    get_template_subject,
    list_templates,
    render_template,
    validate_template,
)


@pytest.fixture
def prospect():
    """Sample prospect for template rendering."""
    return Prospect(
        id=1,
        company_id=1,
        first_name="John",
        last_name="Doe",
        title="VP of Operations",
    )


@pytest.fixture
def company():
    """Sample company for template rendering."""
    return Company(
        id=1,
        name="Acme Lending",
        name_normalized="acme lending",
        state="TX",
        timezone="central",
    )


@pytest.fixture
def sender():
    """Sample sender data."""
    return {
        "name": "Jeff Soderstrom",
        "title": "Account Executive",
        "company": "Nexys LLC",
        "phone": "555-123-4567",
    }


class TestRenderTemplate:
    """Test template rendering."""

    def test_render_intro_template(self, prospect, company, sender):
        """Intro template renders with prospect and company data."""
        html = render_template("intro", prospect, company, sender=sender)
        assert "John" in html
        assert "Acme Lending" in html
        assert "Jeff Soderstrom" in html

    def test_render_follow_up_template(self, prospect, company, sender):
        """Follow-up template renders correctly."""
        html = render_template(
            "follow_up", prospect, company,
            sender=sender, last_contact_date="Feb 1", attempt_count=3,
        )
        assert "John" in html
        assert "Acme Lending" in html

    def test_render_breakup_template(self, prospect, company, sender):
        """Breakup template renders correctly."""
        html = render_template(
            "breakup", prospect, company,
            sender=sender, attempt_count=5,
        )
        assert "John" in html or "Doe" in html
        assert "Acme Lending" in html

    def test_render_demo_invite_template(self, prospect, company, sender):
        """Demo invite template renders with demo data."""
        demo = {
            "date": datetime(2026, 2, 10, 14, 0),
            "duration_minutes": 30,
            "teams_link": "https://teams.microsoft.com/l/meeting/123",
        }
        html = render_template(
            "demo_invite", prospect, company,
            sender=sender, demo=demo,
        )
        assert "John" in html
        assert "teams.microsoft.com" in html

    def test_render_demo_confirmation_template(self, prospect, company, sender):
        """Demo confirmation template renders."""
        demo = {
            "date": datetime(2026, 2, 10, 14, 0),
            "duration_minutes": 30,
            "teams_link": "https://teams.microsoft.com/l/meeting/123",
        }
        html = render_template(
            "demo_confirmation", prospect, company,
            sender=sender, demo=demo,
        )
        assert "John" in html

    def test_render_nurture_1_template(self, prospect, company, sender):
        """Nurture sequence email 1 renders."""
        html = render_template("nurture_1", prospect, company, sender=sender)
        assert "John" in html
        assert "Acme Lending" in html

    def test_render_nurture_2_template(self, prospect, company, sender):
        """Nurture sequence email 2 renders."""
        html = render_template("nurture_2", prospect, company, sender=sender)
        assert "John" in html

    def test_render_nurture_3_template(self, prospect, company, sender):
        """Nurture sequence email 3 renders."""
        html = render_template("nurture_3", prospect, company, sender=sender)
        assert "John" in html

    def test_render_all_templates_without_error(self, prospect, company, sender):
        """Every template in the directory renders without raising."""
        demo = {
            "date": datetime(2026, 2, 10, 14, 0),
            "duration_minutes": 30,
            "teams_link": "https://teams.link/test",
        }
        for name in list_templates():
            html = render_template(
                name, prospect, company,
                sender=sender, demo=demo,
                last_contact_date="Feb 1", attempt_count=3,
            )
            assert len(html) > 0, f"Template {name} rendered empty"

    def test_render_nonexistent_template_raises(self, prospect, company):
        """Rendering a missing template raises TemplateNotFound."""
        import jinja2

        with pytest.raises(jinja2.TemplateNotFound):
            render_template("nonexistent", prospect, company)


class TestGetTemplateSubject:
    """Test subject line generation."""

    def test_intro_subject(self, prospect, company, sender):
        """Intro subject includes both company names."""
        subject = get_template_subject(
            "intro", prospect, company, sender=sender,
        )
        assert "Nexys LLC" in subject
        assert "Acme Lending" in subject

    def test_breakup_subject(self, prospect, company):
        """Breakup subject includes company name."""
        subject = get_template_subject("breakup", prospect, company)
        assert "Acme Lending" in subject

    def test_nurture_subject_includes_name(self, prospect, company):
        """Nurture subjects personalize with first name."""
        subject = get_template_subject("nurture_2", prospect, company)
        assert "John" in subject

    def test_unknown_template_returns_title_case(self, prospect):
        """Unknown template name returns title-cased version."""
        subject = get_template_subject("some_custom_template", prospect)
        assert subject == "Some Custom Template"


class TestListTemplates:
    """Test template listing."""

    def test_lists_all_templates(self):
        """list_templates returns all 8 templates."""
        templates = list_templates()
        assert len(templates) == 8
        assert "intro" in templates
        assert "follow_up" in templates
        assert "demo_confirmation" in templates
        assert "demo_invite" in templates
        assert "nurture_1" in templates
        assert "nurture_2" in templates
        assert "nurture_3" in templates
        assert "breakup" in templates

    def test_templates_are_sorted(self):
        """list_templates returns sorted list."""
        templates = list_templates()
        assert templates == sorted(templates)


class TestValidateTemplate:
    """Test template validation."""

    def test_valid_template(self):
        """Existing valid template returns no issues."""
        issues = validate_template("intro")
        assert issues == []

    def test_nonexistent_template(self):
        """Missing template returns file-not-found issue."""
        issues = validate_template("does_not_exist")
        assert len(issues) == 1
        assert "not found" in issues[0]

    def test_all_templates_valid(self):
        """Every template in the directory passes validation."""
        for name in list_templates():
            issues = validate_template(name)
            assert issues == [], f"Template {name} has issues: {issues}"
