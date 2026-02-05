"""Tests for prospect scoring."""

import pytest
from src.engine.scoring import calculate_score, calculate_confidence, ScoreWeights
from src.db.models import Prospect, Company


class TestScoreWeights:
    """Test score weight configuration."""
    
    def test_default_weights(self):
        """Default weights are defined."""
        weights = ScoreWeights()
        assert weights.company_fit > 0
        assert weights.engagement_signals > 0


class TestCalculateScore:
    """Test score calculation."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_score_range(self, sample_prospect: Prospect, sample_company: Company):
        """Score is in valid range 0-100."""
        score = calculate_score(sample_prospect, sample_company)
        assert 0 <= score <= 100
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_engaged_scores_higher(
        self, 
        sample_prospect: Prospect, 
        sample_engaged_prospect: Prospect,
        sample_company: Company
    ):
        """Engaged prospects score higher than unengaged."""
        pass


class TestCalculateConfidence:
    """Test confidence calculation."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_confidence_with_complete_data(self, sample_prospect: Prospect):
        """Complete data has high confidence."""
        pass
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_confidence_with_missing_data(self):
        """Missing data reduces confidence."""
        pass
