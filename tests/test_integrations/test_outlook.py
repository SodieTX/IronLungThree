"""Tests for Outlook integration."""

import pytest
from src.integrations.outlook import OutlookClient, ReplyClassification


class TestOutlookClient:
    """Test OutlookClient class."""
    
    @pytest.mark.skip(reason="Stub not implemented - requires OAuth")
    @pytest.mark.integration
    def test_health_check(self):
        """Health check returns True when connected."""
        pass
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_is_configured_without_credentials(self):
        """is_configured returns False without credentials."""
        client = OutlookClient()
        assert client.is_configured() is False


class TestReplyClassification:
    """Test reply classification enum."""
    
    def test_all_classifications_exist(self):
        """All expected classifications are defined."""
        assert ReplyClassification.INTERESTED
        assert ReplyClassification.NOT_INTERESTED
        assert ReplyClassification.OOO
        assert ReplyClassification.REFERRAL
        assert ReplyClassification.UNKNOWN
