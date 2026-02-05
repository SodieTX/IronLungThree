"""Integrations package - External service connections.

This package handles all communication with external services:
    - Outlook (email and calendar via Microsoft Graph)
    - Bria (softphone dialing)
    - ActiveCampaign (lead import)
    - Google Search (free tier for research)
    - CSV/XLSX import

Modules:
    - base: Abstract base class for integrations
    - outlook: Microsoft Graph API client
    - bria: Bria softphone integration
    - activecampaign: ActiveCampaign API client
    - google_search: Google Custom Search client
    - csv_importer: CSV/XLSX file parser
    - email_importer: Email CSV importer for enrichment
"""

from src.integrations.base import IntegrationBase

__all__ = [
    "IntegrationBase",
]
