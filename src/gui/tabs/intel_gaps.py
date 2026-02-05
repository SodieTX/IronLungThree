"""Intel gaps tab - Missing information audit."""

from src.gui.tabs import TabBase
from src.core.logging import get_logger

logger = get_logger(__name__)


class IntelGapsTab(TabBase):
    """Missing intel audit."""

    def refresh(self) -> None:
        raise NotImplementedError("Phase 6, Step 6.9")

    def on_activate(self) -> None:
        raise NotImplementedError("Phase 6, Step 6.9")
