"""Tests for population transitions."""

import pytest
from src.engine.populations import (
    can_transition,
    can_transition_stage,
    transition_prospect,
    VALID_TRANSITIONS,
)
from src.db.models import Population, EngagementStage, Prospect


class TestValidTransitions:
    """Test transition validation rules."""
    
    def test_unengaged_can_go_to_engaged(self):
        """Unengaged -> Engaged is valid."""
        assert can_transition(Population.UNENGAGED, Population.ENGAGED)
    
    def test_unengaged_can_go_to_dead_dnc(self):
        """Unengaged -> Dead/DNC is valid."""
        assert can_transition(Population.UNENGAGED, Population.DEAD_DNC)
    
    def test_dead_dnc_cannot_transition_anywhere(self):
        """Dead/DNC cannot transition to any population."""
        for pop in Population:
            if pop != Population.DEAD_DNC:
                assert not can_transition(Population.DEAD_DNC, pop)
    
    def test_engaged_can_go_to_closed_won(self):
        """Engaged -> Closed Won is valid."""
        assert can_transition(Population.ENGAGED, Population.CLOSED_WON)
    
    def test_engaged_can_go_to_lost(self):
        """Engaged -> Lost is valid."""
        assert can_transition(Population.ENGAGED, Population.LOST)


class TestEngagementStages:
    """Test engagement stage transitions."""
    
    def test_pre_demo_to_demo_scheduled(self):
        """Pre-Demo -> Demo Scheduled is valid."""
        assert can_transition_stage(
            EngagementStage.PRE_DEMO, 
            EngagementStage.DEMO_SCHEDULED
        )
    
    def test_cannot_skip_stages(self):
        """Cannot skip from Pre-Demo to Closing."""
        assert not can_transition_stage(
            EngagementStage.PRE_DEMO,
            EngagementStage.CLOSING
        )


class TestTransitionProspect:
    """Test prospect transition function."""
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_transition_updates_prospect(self, sample_prospect: Prospect, memory_db):
        """Transition updates prospect population."""
        pass
    
    @pytest.mark.skip(reason="Stub not implemented")
    def test_dnc_transition_raises_error(self, memory_db):
        """Transitioning FROM DNC raises DNCViolationError."""
        pass
