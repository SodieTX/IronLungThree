"""Tests for command palette — fuzzy search, recent tracking, execution."""

import pytest

from src.gui.adhd.command_palette import CommandPalette, PaletteItem, PaletteResult


def _noop() -> None:
    pass


@pytest.fixture
def palette() -> CommandPalette:
    cp = CommandPalette()
    cp.register_many(
        [
            PaletteItem(label="Pipeline", category="tab", action=_noop),
            PaletteItem(label="Today", category="tab", action=_noop),
            PaletteItem(label="Calendar", category="tab", action=_noop),
            PaletteItem(label="Settings", category="tab", action=_noop),
            PaletteItem(
                label="Send Email",
                category="action",
                action=_noop,
                keywords=["email", "mail", "compose"],
            ),
            PaletteItem(
                label="Schedule Demo",
                category="action",
                action=_noop,
                keywords=["demo", "meeting"],
            ),
            PaletteItem(
                label="John Smith at ABC Lending",
                category="prospect",
                action=_noop,
                keywords=["john", "smith", "abc"],
            ),
            PaletteItem(
                label="Jane Doe at XYZ Mortgage",
                category="prospect",
                action=_noop,
                keywords=["jane", "doe", "xyz"],
            ),
        ]
    )
    return cp


class TestSearch:
    def test_exact_prefix_match(self, palette: CommandPalette) -> None:
        results = palette.search("Pipe")
        assert len(results) > 0
        assert results[0].item.label == "Pipeline"

    def test_substring_match(self, palette: CommandPalette) -> None:
        results = palette.search("mail")
        labels = [r.item.label for r in results]
        assert "Send Email" in labels

    def test_fuzzy_match(self, palette: CommandPalette) -> None:
        results = palette.search("sddmo")  # fuzzy for "Schedule Demo"
        # 's', 'd', 'd', 'm', 'o' — "Schedule Demo" contains s-c-h-e-d-u-l-e-d-e-m-o
        # This tests that fuzzy matching works
        labels = [r.item.label for r in results]
        assert "Schedule Demo" in labels

    def test_keyword_match(self, palette: CommandPalette) -> None:
        results = palette.search("compose")
        labels = [r.item.label for r in results]
        assert "Send Email" in labels

    def test_no_match_returns_empty(self, palette: CommandPalette) -> None:
        results = palette.search("zzzzzznothing")
        assert len(results) == 0

    def test_empty_query_returns_all(self, palette: CommandPalette) -> None:
        results = palette.search("")
        assert len(results) == palette.item_count()

    def test_case_insensitive(self, palette: CommandPalette) -> None:
        results = palette.search("pipeline")
        assert len(results) > 0
        assert results[0].item.label == "Pipeline"

    def test_result_limit(self, palette: CommandPalette) -> None:
        results = palette.search("", limit=3)
        assert len(results) == 3


class TestExecution:
    def test_execute_calls_action(self, palette: CommandPalette) -> None:
        called: list[bool] = []
        item = PaletteItem(label="Test", category="action", action=lambda: called.append(True))
        palette.register(item)
        results = palette.search("Test")
        palette.execute(results[0])
        assert len(called) == 1

    def test_execute_tracks_recent(self, palette: CommandPalette) -> None:
        results = palette.search("Pipeline")
        palette.execute(results[0])
        recent = palette.get_recent()
        assert recent[0] == "Pipeline"

    def test_recent_deduplicates(self, palette: CommandPalette) -> None:
        results = palette.search("Pipeline")
        palette.execute(results[0])
        palette.execute(results[0])
        recent = palette.get_recent()
        assert recent.count("Pipeline") == 1


class TestRecencyBoost:
    def test_recent_items_rank_higher(self, palette: CommandPalette) -> None:
        # Execute "Settings" to make it recent
        results = palette.search("Settings")
        palette.execute(results[0])

        # Now search empty — recent should be first
        all_results = palette.search("")
        assert all_results[0].item.label == "Settings"


class TestRegistration:
    def test_register_single(self) -> None:
        cp = CommandPalette()
        cp.register(PaletteItem(label="Test", category="action", action=_noop))
        assert cp.item_count() == 1

    def test_register_many(self) -> None:
        cp = CommandPalette()
        items = [PaletteItem(label=f"Item {i}", category="action", action=_noop) for i in range(5)]
        cp.register_many(items)
        assert cp.item_count() == 5

    def test_clear(self, palette: CommandPalette) -> None:
        palette.clear()
        assert palette.item_count() == 0


class TestPerformance:
    def test_search_500_items_fast(self) -> None:
        """Command palette search with 500 items should be < 50ms."""
        import time

        cp = CommandPalette()
        for i in range(500):
            cp.register(
                PaletteItem(
                    label=f"Prospect {i} at Company {i}",
                    category="prospect",
                    action=_noop,
                    keywords=[f"keyword{i}", f"tag{i}"],
                )
            )

        start = time.perf_counter()
        results = cp.search("prospect 42")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(results) > 0
        assert elapsed_ms < 50, f"Search took {elapsed_ms:.1f}ms, expected < 50ms"
