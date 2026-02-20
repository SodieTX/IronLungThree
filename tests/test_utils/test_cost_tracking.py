"""Tests for Claude API cost tracking."""

import json
import threading
from datetime import date, datetime
from pathlib import Path

import pytest

from src.utils.cost_tracking import (
    APICallRecord,
    CostTracker,
    UsageSummary,
    _estimate_cost,
    reset_tracker,
)


@pytest.fixture
def usage_file(tmp_path):
    """Provide a temp JSONL file for cost tracking."""
    return tmp_path / "test_usage.jsonl"


@pytest.fixture
def tracker(usage_file):
    """Provide a fresh CostTracker."""
    reset_tracker()
    return CostTracker(usage_file)


class TestEstimateCost:
    """Test cost estimation logic."""

    def test_sonnet_pricing(self):
        """Sonnet model uses $3/$15 per million tokens."""
        cost = _estimate_cost("claude-sonnet-4-20250514", 1_000_000, 0)
        assert cost == 3.0

    def test_sonnet_output_pricing(self):
        """Sonnet output tokens cost $15 per million."""
        cost = _estimate_cost("claude-sonnet-4-20250514", 0, 1_000_000)
        assert cost == 15.0

    def test_opus_pricing(self):
        """Opus model uses $15/$75 per million tokens."""
        cost = _estimate_cost("claude-opus-4-20250514", 1_000_000, 0)
        assert cost == 15.0

    def test_haiku_pricing(self):
        """Haiku model uses $0.25/$1.25 per million tokens."""
        cost = _estimate_cost("claude-haiku-4-5-20251001", 1_000_000, 0)
        assert cost == 0.25

    def test_unknown_model_defaults_to_sonnet(self):
        """Unknown models default to sonnet pricing."""
        cost = _estimate_cost("some-unknown-model", 1_000_000, 0)
        assert cost == 3.0

    def test_mixed_tokens(self):
        """Mixed input/output tokens calculate correctly."""
        # 1000 input + 500 output on sonnet
        # (1000 * 3.0 + 500 * 15.0) / 1_000_000 = 0.0105
        cost = _estimate_cost("claude-sonnet-4-20250514", 1000, 500)
        assert abs(cost - 0.0105) < 0.0001

    def test_zero_tokens(self):
        """Zero tokens returns zero cost."""
        cost = _estimate_cost("claude-sonnet-4-20250514", 0, 0)
        assert cost == 0.0


class TestCostTracker:
    """Test the CostTracker class."""

    def test_record_call_creates_file(self, tracker, usage_file):
        """Recording a call creates the JSONL file."""
        assert not usage_file.exists()
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1500, 300)
        assert usage_file.exists()

    def test_record_call_appends_json(self, tracker, usage_file):
        """Each record is one JSON line."""
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1500, 300)
        tracker.record_call("copilot", "claude-sonnet-4-20250514", 2000, 500)

        lines = usage_file.read_text().strip().split("\n")
        assert len(lines) == 2

        record1 = json.loads(lines[0])
        assert record1["caller"] == "anne"
        assert record1["input_tokens"] == 1500
        assert record1["output_tokens"] == 300

        record2 = json.loads(lines[1])
        assert record2["caller"] == "copilot"

    def test_record_call_returns_record(self, tracker):
        """record_call returns the APICallRecord."""
        record = tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)
        assert isinstance(record, APICallRecord)
        assert record.caller == "anne"
        assert record.model == "claude-sonnet-4-20250514"
        assert record.input_tokens == 1000
        assert record.output_tokens == 200
        assert record.estimated_cost > 0

    def test_record_call_estimated_cost(self, tracker):
        """Estimated cost matches _estimate_cost calculation."""
        record = tracker.record_call("email_gen", "claude-sonnet-4-20250514", 5000, 1000)
        expected = _estimate_cost("claude-sonnet-4-20250514", 5000, 1000)
        assert record.estimated_cost == round(expected, 6)

    def test_record_call_creates_parent_dirs(self, tmp_path):
        """record_call creates parent directories if needed."""
        deep_file = tmp_path / "a" / "b" / "c" / "usage.jsonl"
        tracker = CostTracker(deep_file)
        tracker.record_call("anne", "claude-sonnet-4-20250514", 100, 50)
        assert deep_file.exists()

    def test_get_today_summary_empty(self, tracker):
        """Today summary with no records returns zeros."""
        summary = tracker.get_today_summary()
        assert summary.total_calls == 0
        assert summary.total_cost == 0.0
        assert summary.period == date.today().isoformat()

    def test_get_today_summary(self, tracker):
        """Today summary counts today's calls."""
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)
        tracker.record_call("copilot", "claude-sonnet-4-20250514", 2000, 300)

        summary = tracker.get_today_summary()
        assert summary.total_calls == 2
        assert summary.total_input_tokens == 3000
        assert summary.total_output_tokens == 500
        assert summary.total_cost > 0
        assert "anne" in summary.by_caller
        assert "copilot" in summary.by_caller

    def test_get_monthly_summary(self, tracker):
        """Monthly summary aggregates correctly."""
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)

        today = date.today()
        summary = tracker.get_monthly_summary(today.year, today.month)
        assert summary.total_calls == 1

    def test_get_monthly_summary_wrong_month(self, tracker):
        """Monthly summary for a different month returns zeros."""
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)

        # Query for a month that definitely doesn't have records
        summary = tracker.get_monthly_summary(2020, 1)
        assert summary.total_calls == 0

    def test_get_total_summary(self, tracker):
        """Total summary counts all records."""
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)
        tracker.record_call("copilot", "claude-opus-4-20250514", 500, 100)
        tracker.record_call("email_gen", "claude-haiku-4-5-20251001", 800, 150)

        summary = tracker.get_total_summary()
        assert summary.total_calls == 3
        assert summary.period == "all-time"
        assert len(summary.by_caller) == 3

    def test_by_caller_breakdown(self, tracker):
        """by_caller tracks cost per module."""
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1500, 300)
        tracker.record_call("copilot", "claude-sonnet-4-20250514", 2000, 400)

        summary = tracker.get_total_summary()
        assert summary.by_caller["anne"] > summary.by_caller["copilot"]

    def test_corrupt_lines_skipped(self, tracker, usage_file):
        """Corrupt JSON lines are silently skipped."""
        # Write some corrupt data
        with open(usage_file, "w") as f:
            f.write("not json\n")
            f.write('{"caller": "missing fields"}\n')

        # Add a valid record
        tracker.record_call("anne", "claude-sonnet-4-20250514", 1000, 200)

        summary = tracker.get_total_summary()
        assert summary.total_calls == 1  # Only the valid record

    def test_empty_lines_skipped(self, tracker, usage_file):
        """Empty lines in the JSONL are skipped."""
        # Write with some empty lines
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(usage_file, "w") as f:
            f.write("\n\n\n")

        summary = tracker.get_total_summary()
        assert summary.total_calls == 0

    def test_concurrent_writes(self, tracker, usage_file):
        """Multiple threads can write without corruption."""
        errors = []

        def write_records():
            try:
                for _ in range(10):
                    tracker.record_call("test", "claude-sonnet-4-20250514", 100, 50)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_records) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # All 40 records should be present
        lines = [line for line in usage_file.read_text().strip().split("\n") if line]
        assert len(lines) == 40


class TestUsageSummary:
    """Test UsageSummary dataclass."""

    def test_default_by_caller(self):
        """by_caller defaults to empty dict."""
        summary = UsageSummary(period="test")
        assert summary.by_caller == {}

    def test_fields(self):
        """All fields are accessible."""
        summary = UsageSummary(
            period="2026-02",
            total_calls=5,
            total_input_tokens=10000,
            total_output_tokens=2000,
            total_cost=0.15,
        )
        assert summary.period == "2026-02"
        assert summary.total_calls == 5
