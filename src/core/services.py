"""Service registry for tracking integration availability.

Central registry that tracks which external services are configured,
available, and healthy. Prevents runtime crashes from missing credentials
by providing clear status checks before any API call is attempted.

Every integration registers itself here at startup. The GUI, engine,
and autonomous layers check the registry before attempting operations
that require external services.

Usage:
    from src.core.services import get_service_registry, ServiceStatus

    registry = get_service_registry()
    status = registry.check("outlook")
    if status.available:
        # safe to use OutlookClient
        ...
    else:
        # show user what's missing
        print(status.reason)

    # Quick boolean gate
    if registry.is_available("claude"):
        gen = EmailGenerator()
        ...

    # Full readiness report (for settings screen / CLI diagnostics)
    report = registry.readiness_report()
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.core.config import get_config
from src.core.logging import get_logger

logger = get_logger(__name__)


class ServicePhase(Enum):
    """Which build phase a service belongs to."""

    PHASE_1 = 1  # Core / local-only
    PHASE_3 = 3  # Outlook, Bria
    PHASE_4 = 4  # Claude AI
    PHASE_5 = 5  # ActiveCampaign, Google Search


@dataclass
class ServiceStatus:
    """Status of a single service.

    Attributes:
        name: Human-readable service name
        service_key: Registry lookup key
        phase: Build phase this service belongs to
        configured: Whether credentials are present
        available: Whether the service can be used right now
        reason: Why the service is unavailable (empty if available)
        credentials_present: Which credential fields are set
        credentials_missing: Which credential fields are missing
    """

    name: str
    service_key: str
    phase: ServicePhase
    configured: bool = False
    available: bool = False
    reason: str = ""
    credentials_present: list[str] = field(default_factory=list)
    credentials_missing: list[str] = field(default_factory=list)


@dataclass
class ReadinessReport:
    """Full readiness report across all phases.

    Attributes:
        services: Status of every registered service
        phase_ready: Which phases have all services configured
        summary: Human-readable summary string
    """

    services: list[ServiceStatus] = field(default_factory=list)
    phase_ready: dict[int, bool] = field(default_factory=dict)
    summary: str = ""


class ServiceRegistry:
    """Central registry of all external service integrations.

    Checks config once, caches results, provides clear status
    for every service the app depends on.
    """

    def __init__(self) -> None:
        self._statuses: dict[str, ServiceStatus] = {}
        self._refresh()

    def _refresh(self) -> None:
        """Re-check all service configurations against current config."""
        config = get_config()
        self._statuses.clear()

        # ------------------------------------------------------------------
        # Phase 3: Outlook
        # ------------------------------------------------------------------
        outlook_creds = {
            "OUTLOOK_CLIENT_ID": config.outlook_client_id,
            "OUTLOOK_CLIENT_SECRET": config.outlook_client_secret,
            "OUTLOOK_TENANT_ID": config.outlook_tenant_id,
            "OUTLOOK_USER_EMAIL": config.outlook_user_email,
        }
        outlook_present = [k for k, v in outlook_creds.items() if v]
        outlook_missing = [k for k, v in outlook_creds.items() if not v]
        outlook_configured = len(outlook_missing) == 0

        # Partial credentials are a specific problem worth calling out
        if outlook_present and outlook_missing:
            outlook_reason = (
                f"Partial Outlook config: have {', '.join(outlook_present)} "
                f"but missing {', '.join(outlook_missing)}"
            )
        elif outlook_missing:
            outlook_reason = "Outlook not configured (no credentials set)"
        else:
            outlook_reason = ""

        self._statuses["outlook"] = ServiceStatus(
            name="Microsoft Outlook (Graph API)",
            service_key="outlook",
            phase=ServicePhase.PHASE_3,
            configured=outlook_configured,
            available=outlook_configured,
            reason=outlook_reason,
            credentials_present=outlook_present,
            credentials_missing=outlook_missing,
        )

        # ------------------------------------------------------------------
        # Phase 3: Bria (no credentials needed, always available)
        # ------------------------------------------------------------------
        self._statuses["bria"] = ServiceStatus(
            name="Bria Softphone",
            service_key="bria",
            phase=ServicePhase.PHASE_3,
            configured=True,
            available=True,
            reason="",
            credentials_present=[],
            credentials_missing=[],
        )

        # ------------------------------------------------------------------
        # Phase 4: Claude AI
        # ------------------------------------------------------------------
        claude_creds = {"CLAUDE_API_KEY": config.claude_api_key}
        claude_present = [k for k, v in claude_creds.items() if v]
        claude_missing = [k for k, v in claude_creds.items() if not v]
        claude_configured = len(claude_missing) == 0

        self._statuses["claude"] = ServiceStatus(
            name="Claude AI (Anthropic)",
            service_key="claude",
            phase=ServicePhase.PHASE_4,
            configured=claude_configured,
            available=claude_configured,
            reason="" if claude_configured else "CLAUDE_API_KEY not set",
            credentials_present=claude_present,
            credentials_missing=claude_missing,
        )

        # ------------------------------------------------------------------
        # Phase 5: ActiveCampaign
        # ------------------------------------------------------------------
        ac_creds = {
            "ACTIVECAMPAIGN_API_KEY": config.activecampaign_api_key,
            "ACTIVECAMPAIGN_URL": config.activecampaign_url,
        }
        ac_present = [k for k, v in ac_creds.items() if v]
        ac_missing = [k for k, v in ac_creds.items() if not v]
        ac_configured = len(ac_missing) == 0

        if ac_present and ac_missing:
            ac_reason = (
                f"Partial ActiveCampaign config: have {', '.join(ac_present)} "
                f"but missing {', '.join(ac_missing)}"
            )
        elif ac_missing:
            ac_reason = "ActiveCampaign not configured"
        else:
            ac_reason = ""

        self._statuses["activecampaign"] = ServiceStatus(
            name="ActiveCampaign",
            service_key="activecampaign",
            phase=ServicePhase.PHASE_5,
            configured=ac_configured,
            available=ac_configured,
            reason=ac_reason,
            credentials_present=ac_present,
            credentials_missing=ac_missing,
        )

        # ------------------------------------------------------------------
        # Phase 5: Google Custom Search
        # ------------------------------------------------------------------
        # Google Search credentials aren't in Config yet (Phase 5 stub),
        # so this is always unavailable for now.
        self._statuses["google_search"] = ServiceStatus(
            name="Google Custom Search",
            service_key="google_search",
            phase=ServicePhase.PHASE_5,
            configured=False,
            available=False,
            reason="Google Search not yet implemented (Phase 5)",
            credentials_present=[],
            credentials_missing=["GOOGLE_API_KEY", "GOOGLE_CX"],
        )

    def check(self, service_key: str) -> ServiceStatus:
        """Check status of a specific service.

        Args:
            service_key: Service identifier (e.g. "outlook", "claude")

        Returns:
            ServiceStatus for the requested service

        Raises:
            KeyError: If service_key is not registered
        """
        if service_key not in self._statuses:
            raise KeyError(
                f"Unknown service '{service_key}'. "
                f"Known services: {', '.join(sorted(self._statuses.keys()))}"
            )
        return self._statuses[service_key]

    def is_available(self, service_key: str) -> bool:
        """Quick boolean check: can this service be used right now?

        Args:
            service_key: Service identifier

        Returns:
            True if the service is fully configured and available
        """
        try:
            return self.check(service_key).available
        except KeyError:
            return False

    def require(self, service_key: str) -> None:
        """Assert that a service is available, or raise with a clear message.

        Use this at the top of functions that absolutely need a service.

        Args:
            service_key: Service identifier

        Raises:
            ConfigurationError: If the service is not available
        """
        from src.core.exceptions import ConfigurationError

        status = self.check(service_key)
        if not status.available:
            raise ConfigurationError(
                f"{status.name} is not available: {status.reason}"
            )

    def readiness_report(self) -> ReadinessReport:
        """Generate a full readiness report for all services.

        Returns:
            ReadinessReport with per-service status and phase rollups
        """
        services = list(self._statuses.values())

        # Calculate phase readiness
        phase_services: dict[int, list[bool]] = {}
        for svc in services:
            phase_num = svc.phase.value
            if phase_num not in phase_services:
                phase_services[phase_num] = []
            phase_services[phase_num].append(svc.configured)

        phase_ready = {
            phase: all(statuses)
            for phase, statuses in phase_services.items()
        }

        # Build summary
        lines = []
        for phase_num in sorted(phase_services.keys()):
            ready = phase_ready[phase_num]
            marker = "READY" if ready else "NOT READY"
            lines.append(f"  Phase {phase_num}: {marker}")

            for svc in services:
                if svc.phase.value == phase_num:
                    icon = "+" if svc.configured else "-"
                    detail = svc.reason if svc.reason else "configured"
                    lines.append(f"    [{icon}] {svc.name}: {detail}")

        summary = "\n".join(lines)

        return ReadinessReport(
            services=services,
            phase_ready=phase_ready,
            summary=summary,
        )

    def log_status(self) -> None:
        """Log the current service status at startup."""
        report = self.readiness_report()

        for svc in report.services:
            if svc.available:
                logger.info(
                    f"Service ready: {svc.name}",
                    extra={"context": {"service": svc.service_key}},
                )
            elif svc.credentials_present and svc.credentials_missing:
                # Partial config is a warning - likely a mistake
                logger.warning(
                    f"Service partially configured: {svc.name} - {svc.reason}",
                    extra={"context": {
                        "service": svc.service_key,
                        "present": svc.credentials_present,
                        "missing": svc.credentials_missing,
                    }},
                )
            else:
                # Completely unconfigured is normal during development
                logger.info(
                    f"Service not configured: {svc.name} (Phase {svc.phase.value})",
                    extra={"context": {"service": svc.service_key}},
                )


# Singleton
_registry: Optional[ServiceRegistry] = None


def get_service_registry() -> ServiceRegistry:
    """Return the cached ServiceRegistry singleton.

    Returns:
        ServiceRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ServiceRegistry()
    return _registry


def reset_service_registry() -> None:
    """Reset the cached registry. Used for testing."""
    global _registry
    _registry = None
