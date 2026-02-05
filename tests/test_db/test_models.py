"""Tests for data models."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from src.db.models import (
    Activity,
    ActivityType,
    Company,
    ContactMethod,
    ContactMethodType,
    EngagementStage,
    Population,
    Prospect,
    assess_completeness,
    normalize_company_name,
    timezone_from_state,
)


class TestPopulationEnum:
    """Test Population enum."""

    def test_all_populations_exist(self):
        """All expected populations are defined."""
        assert Population.BROKEN
        assert Population.DEAD_DNC
        assert Population.UNENGAGED
        assert Population.ENGAGED
        assert Population.CLOSED_WON
        assert Population.LOST
        assert Population.PARKED
        assert Population.PARTNERSHIP

    def test_population_values_are_strings(self):
        """Population values are lowercase strings."""
        assert Population.BROKEN.value == "broken"
        assert Population.DEAD_DNC.value == "dead_dnc"


class TestEngagementStageEnum:
    """Test EngagementStage enum."""

    def test_all_stages_exist(self):
        """All engagement stages are defined."""
        assert EngagementStage.PRE_DEMO
        assert EngagementStage.DEMO_SCHEDULED
        assert EngagementStage.POST_DEMO
        assert EngagementStage.CLOSING


class TestCompanyModel:
    """Test Company dataclass."""

    def test_company_creation(self, sample_company: Company):
        """Company can be created with fields."""
        assert sample_company.name == "Acme Corp"
        assert sample_company.state == "CO"

    def test_company_default_id_is_none(self):
        """New company has None id."""
        company = Company(name="Test Co")
        assert company.id is None


class TestProspectModel:
    """Test Prospect dataclass."""

    def test_prospect_creation(self, sample_prospect: Prospect):
        """Prospect can be created with fields."""
        assert sample_prospect.first_name == "John"
        assert sample_prospect.population == Population.UNENGAGED

    def test_prospect_full_name(self, sample_prospect: Prospect):
        """full_name property works."""
        assert sample_prospect.full_name == "John Doe"

    def test_prospect_full_name_single_name(self):
        """full_name handles single name."""
        prospect = Prospect(first_name="Madonna", company_id=1)
        assert prospect.full_name == "Madonna"


class TestUtilityFunctions:
    """Test model utility functions."""

    def test_timezone_from_state_known(self):
        """Known state returns timezone."""
        assert timezone_from_state("CO") == "mountain"
        assert timezone_from_state("CA") == "pacific"
        assert timezone_from_state("NY") == "eastern"

    def test_timezone_from_state_unknown(self):
        """Unknown state returns central default."""
        assert timezone_from_state("XX") == "central"

    def test_normalize_company_name(self):
        """Company name normalization."""
        # Strips legal suffixes only
        assert normalize_company_name("Acme Corp.") == "acme"
        assert normalize_company_name("Widget LLC") == "widget"

    @pytest.mark.skip(reason="Stub not implemented")
    def test_assess_completeness_full_data(self):
        """Full prospect returns 100 confidence."""
        pass
