"""Content generation package.

Generates:
    - Morning brief
    - Daily cockpit data
    - End-of-day summary
"""

from src.content.morning_brief import MorningBrief, generate_morning_brief
from src.content.eod_summary import EODSummary, generate_eod_summary
from src.content.daily_cockpit import CockpitData, get_cockpit_data

__all__ = [
    "MorningBrief",
    "generate_morning_brief",
    "EODSummary",
    "generate_eod_summary",
    "CockpitData",
    "get_cockpit_data",
]
