"""AI Copilot for strategic conversation mode.

Deeper conversational mode for questions like:
    - "What's our pipeline looking like?"
    - "What's the story with ABC Lending?"
    - "I've got a demo tomorrow, what should I know?"

Also supports record manipulation via conversation (Step 7.2):
    - "Move John Smith to engaged"
    - "Set follow-up for Jane Doe to next Tuesday"
    - "Park ABC Lending until March"
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from src.ai.claude_client import ClaudeClientMixin
from src.core.config import CLAUDE_MODEL, get_config
from src.core.logging import get_logger
from src.db.database import Database
from src.db.models import EngagementStage, Population

logger = get_logger(__name__)


@dataclass
class CopilotResponse:
    """Response from copilot interaction.

    Attributes:
        message: The text response
        action_taken: Description of any DB action performed
        tokens_used: API tokens consumed (0 if local-only)
    """

    message: str
    action_taken: Optional[str] = None
    tokens_used: int = 0


class Copilot(ClaudeClientMixin):
    """Strategic AI conversation mode.

    Provides pipeline intelligence and can manipulate records
    through natural language commands.
    """

    def __init__(self, db: Database):
        self.db = db
        self._config = get_config()
        self._client: Optional[object] = None

    def _get_claude_config(self):
        return self._config

    def ask(self, question: str) -> CopilotResponse:
        """Answer strategic question about pipeline.

        Handles both analytical questions (uses AI if available)
        and command-style requests (record manipulation).

        Args:
            question: The user's question or command

        Returns:
            CopilotResponse with answer and any action taken
        """
        question_lower = question.lower().strip()

        # Check for record manipulation commands first (no AI needed)
        action_response = self._try_record_manipulation(question_lower, question)
        if action_response:
            return action_response

        # For analytical questions, build context and respond
        if any(
            kw in question_lower
            for kw in ("pipeline", "overview", "summary", "how are we", "looking like")
        ):
            return self._pipeline_response()

        if any(
            kw in question_lower for kw in ("story", "what about", "tell me about", "status of")
        ):
            return self._entity_lookup(question)

        if any(kw in question_lower for kw in ("demo", "prepare", "briefing", "meeting")):
            return self._demo_prep(question)

        if any(
            kw in question_lower
            for kw in ("decay", "overdue", "stale", "problems", "issues", "trouble")
        ):
            return self._decay_report()

        if any(kw in question_lower for kw in ("win", "loss", "pattern", "learning", "trend")):
            return self._learning_report()

        # If AI is available, use it for open-ended questions
        if self.is_available():
            return self._ai_response(question)

        # Fallback for unrecognized questions without AI
        return CopilotResponse(
            message=(
                "I can help with:\n"
                "- Pipeline overview: 'What's our pipeline looking like?'\n"
                "- Company/prospect info: 'What's the story with [name]?'\n"
                "- Demo prep: 'I have a demo with [name] tomorrow'\n"
                "- Pipeline health: 'Any problems I should know about?'\n"
                "- Deal patterns: 'What are our win/loss patterns?'\n"
                "- Record updates: 'Move [name] to engaged'\n"
                "\nFor deeper analysis, configure CLAUDE_API_KEY."
            )
        )

    def pipeline_summary(self) -> str:
        """Generate pipeline overview."""
        pop_counts = self.db.get_population_counts()
        total = sum(pop_counts.values())

        lines = [f"Pipeline: {total} total prospects\n"]

        active_pops = [
            (Population.ENGAGED, "Engaged"),
            (Population.UNENGAGED, "Unengaged"),
            (Population.BROKEN, "Broken"),
            (Population.PARKED, "Parked"),
        ]
        for pop, label in active_pops:
            count = pop_counts.get(pop, 0)
            if count > 0:
                lines.append(f"  {label}: {count}")

        terminal_pops = [
            (Population.CLOSED_WON, "Won"),
            (Population.LOST, "Lost"),
            (Population.DEAD_DNC, "DNC"),
        ]
        terminal = []
        for pop, label in terminal_pops:
            count = pop_counts.get(pop, 0)
            if count > 0:
                terminal.append(f"{label}: {count}")
        if terminal:
            lines.append(f"  ({', '.join(terminal)})")

        # Add decay summary
        from src.engine.intervention import InterventionEngine

        engine = InterventionEngine(self.db)
        report = engine.detect_decay()
        if report.total_issues > 0:
            lines.append(f"\nAttention needed: {report.total_issues} issues")
            if report.overdue_followups:
                lines.append(f"  Overdue follow-ups: {len(report.overdue_followups)}")
            if report.stale_engaged:
                lines.append(f"  Stale engaged: {len(report.stale_engaged)}")
            if report.unworked:
                lines.append(f"  Unworked cards: {len(report.unworked)}")

        return "\n".join(lines)

    def company_story(self, company_id: int) -> str:
        """Generate company/prospect story."""
        company = self.db.get_company(company_id)
        if not company:
            return "Company not found."

        prospects = self.db.get_prospects(company_id=company_id)
        if not prospects:
            return f"{company.name}: No prospects on file."

        lines = [f"{company.name} ({company.state or 'Unknown state'})\n"]

        for p in prospects:
            stage_str = f" ({p.engagement_stage.value})" if p.engagement_stage else ""
            lines.append(
                f"  {p.full_name} — {p.population.value}{stage_str}, " f"score {p.prospect_score}"
            )

            # Get recent activity
            if p.id is None:
                continue
            activities = self.db.get_activities(p.id, limit=3)
            for act in activities:
                act_date = str(act.created_at)[:10] if act.created_at else "unknown"
                notes_preview = ""
                if act.notes:
                    notes_preview = (
                        f": {act.notes[:60]}..." if len(act.notes) > 60 else f": {act.notes}"
                    )
                lines.append(f"    {act_date} — {act.activity_type.value}{notes_preview}")

        return "\n".join(lines)

    def demo_briefing(self, prospect_id: int) -> str:
        """Generate pre-demo briefing."""
        prospect_full = self.db.get_prospect_full(prospect_id)
        if not prospect_full:
            return "Prospect not found."

        p = prospect_full.prospect
        company = prospect_full.company
        nuggets = self.db.get_intel_nuggets(prospect_id)

        lines = [
            f"Demo Briefing: {p.full_name}",
            f"Company: {company.name if company else 'Unknown'}",
            f"Title: {p.title or 'Unknown'}",
            f"Score: {p.prospect_score}, Confidence: {p.data_confidence}",
            "",
        ]

        # Intel
        if nuggets:
            lines.append("Intel:")
            for n in nuggets:
                lines.append(f"  [{n.category.value}] {n.content}")
            lines.append("")

        # Key activity history
        if prospect_full.activities:
            lines.append("Recent history:")
            for act in prospect_full.activities[:5]:
                act_date = str(act.created_at)[:10] if act.created_at else ""
                lines.append(f"  {act_date} {act.activity_type.value}: {act.notes or ''}")
            lines.append("")

        # Strategic insights
        from src.ai.insights import generate_insights

        insights = generate_insights(self.db, prospect_id)
        lines.append(f"Approach: {insights.best_approach}")
        if insights.likely_objections:
            lines.append("Watch for:")
            for obj in insights.likely_objections:
                lines.append(f"  - {obj}")
        if insights.competitive_vulnerabilities:
            lines.append("Competitive angle:")
            for vuln in insights.competitive_vulnerabilities:
                lines.append(f"  - {vuln}")

        return "\n".join(lines)

    # =========================================================================
    # RECORD MANIPULATION (Step 7.2)
    # =========================================================================

    def _try_record_manipulation(
        self, question_lower: str, original: str
    ) -> Optional[CopilotResponse]:
        """Try to parse and execute a record manipulation command.

        Returns None if the input isn't a recognized command.
        """
        # "Move [name] to [population]"
        move_match = re.search(
            r"move\s+(.+?)\s+to\s+(engaged|unengaged|broken|parked|lost|partnership)",
            question_lower,
        )
        if move_match:
            return self._handle_move(move_match.group(1).strip(), move_match.group(2).strip())

        # "Set follow-up for [name] to [date]"
        followup_match = re.search(
            r"(?:set|schedule)\s+(?:follow[\s-]?up|fu)\s+(?:for\s+)?(.+?)\s+(?:to|for|on)\s+(.+)",
            question_lower,
        )
        if followup_match:
            return self._handle_set_followup(
                followup_match.group(1).strip(), followup_match.group(2).strip()
            )

        # "Park [name] until [month]"
        park_match = re.search(
            r"park\s+(.+?)\s+(?:until|til|to)\s+(.+)",
            question_lower,
        )
        if park_match:
            return self._handle_park(park_match.group(1).strip(), park_match.group(2).strip())

        return None

    def _find_prospect_by_name(self, name: str):
        """Find a prospect by partial name match."""
        prospects = self.db.get_prospects(search_query=name, limit=5)
        if not prospects and " " in name:
            # Full name didn't match — try last name alone
            parts = name.strip().split()
            prospects = self.db.get_prospects(search_query=parts[-1], limit=5)
        if not prospects:
            return None, f"No prospect found matching '{name}'."
        if len(prospects) == 1:
            return prospects[0], None
        # Multiple matches — list them
        names = [f"  - {p.full_name} ({p.population.value}, ID: {p.id})" for p in prospects[:5]]
        return None, f"Multiple matches for '{name}':\n" + "\n".join(names) + "\nBe more specific."

    def _handle_move(self, name: str, target_pop: str) -> CopilotResponse:
        """Handle 'move [name] to [population]' command."""
        prospect, error = self._find_prospect_by_name(name)
        if error:
            return CopilotResponse(message=error)

        pop_map = {
            "engaged": Population.ENGAGED,
            "unengaged": Population.UNENGAGED,
            "broken": Population.BROKEN,
            "parked": Population.PARKED,
            "lost": Population.LOST,
            "partnership": Population.PARTNERSHIP,
        }
        target = pop_map.get(target_pop)
        if not target:
            return CopilotResponse(message=f"Unknown population: {target_pop}")

        from src.engine.populations import can_transition, transition_prospect

        if not can_transition(prospect.population, target):
            return CopilotResponse(
                message=(
                    f"Can't move {prospect.full_name} from "
                    f"{prospect.population.value} to {target.value}. "
                    f"That transition isn't allowed."
                )
            )

        try:
            transition_prospect(
                self.db, prospect.id, target, reason=f"Copilot: moved to {target.value}"
            )
            action = (
                f"Moved {prospect.full_name} from {prospect.population.value} to {target.value}"
            )
            return CopilotResponse(
                message=f"Done. {action}.",
                action_taken=action,
            )
        except Exception as e:
            return CopilotResponse(message=f"Failed to move prospect: {e}")

    def _handle_set_followup(self, name: str, date_str: str) -> CopilotResponse:
        """Handle 'set follow-up for [name] to [date]' command."""
        prospect, error = self._find_prospect_by_name(name)
        if error:
            return CopilotResponse(message=error)

        parsed_date = self._parse_date(date_str)
        if not parsed_date:
            return CopilotResponse(
                message=f"Couldn't parse date '{date_str}'. Try YYYY-MM-DD or 'next Tuesday'."
            )

        from src.engine.cadence import set_follow_up

        set_follow_up(self.db, prospect.id, parsed_date, reason="Copilot: follow-up set")
        date_display = parsed_date.strftime("%Y-%m-%d")
        action = f"Set follow-up for {prospect.full_name} to {date_display}"
        return CopilotResponse(
            message=f"Done. {action}.",
            action_taken=action,
        )

    def _handle_park(self, name: str, month_str: str) -> CopilotResponse:
        """Handle 'park [name] until [month]' command."""
        prospect, error = self._find_prospect_by_name(name)
        if error:
            return CopilotResponse(message=error)

        # Parse month (e.g., "march", "2025-03", "march 2025")
        parsed_month = self._parse_month(month_str)
        if not parsed_month:
            return CopilotResponse(
                message=f"Couldn't parse month '{month_str}'. Try 'March' or '2025-03'."
            )

        from src.engine.populations import can_transition, transition_prospect

        if not can_transition(prospect.population, Population.PARKED):
            return CopilotResponse(
                message=f"Can't park {prospect.full_name} from {prospect.population.value}."
            )

        try:
            prospect.parked_month = parsed_month
            self.db.update_prospect(prospect)
            transition_prospect(
                self.db,
                prospect.id,
                Population.PARKED,
                reason=f"Copilot: parked until {parsed_month}",
            )
            action = f"Parked {prospect.full_name} until {parsed_month}"
            return CopilotResponse(
                message=f"Done. {action}.",
                action_taken=action,
            )
        except Exception as e:
            return CopilotResponse(message=f"Failed to park prospect: {e}")

    # =========================================================================
    # ANALYTICAL RESPONSES
    # =========================================================================

    def _pipeline_response(self) -> CopilotResponse:
        """Generate pipeline overview response."""
        summary = self.pipeline_summary()
        return CopilotResponse(message=summary)

    def _entity_lookup(self, question: str) -> CopilotResponse:
        """Look up a company or prospect mentioned in the question."""
        # Strip common prefixes
        cleaned = (
            re.sub(
                r"^(what'?s?\s+the\s+story\s+with|tell\s+me\s+about|what\s+about|status\s+of)\s+",
                "",
                question.strip(),
                flags=re.IGNORECASE,
            )
            .strip()
            .rstrip("?")
        )

        # Try company search first
        companies = self.db.search_companies(cleaned, limit=3)
        if companies and companies[0].id is not None:
            story = self.company_story(companies[0].id)
            return CopilotResponse(message=story)

        # Try prospect search
        prospects = self.db.get_prospects(search_query=cleaned, limit=3)
        if prospects:
            p = prospects[0]
            if p.id is not None:
                full = self.db.get_prospect_full(p.id)
                if full and full.company and full.company.id is not None:
                    story = self.company_story(full.company.id)
                    return CopilotResponse(message=story)
            return CopilotResponse(
                message=f"{p.full_name}: {p.population.value}, score {p.prospect_score}"
            )

        return CopilotResponse(message=f"No company or prospect found matching '{cleaned}'.")

    def _demo_prep(self, question: str) -> CopilotResponse:
        """Generate demo briefing from question context."""
        # Extract name from question
        cleaned = (
            re.sub(
                r"^(i'?(?:ve\s+)?(?:got|have)\s+a?\s*demo\s+(?:with|for)|"
                r"prepare\s+(?:for|me\s+for)\s+(?:a?\s*)?(?:demo|meeting)\s+with|"
                r"briefing\s+(?:for|on))\s+",
                "",
                question.strip(),
                flags=re.IGNORECASE,
            )
            .strip()
            .rstrip("?")
        )

        # Remove trailing temporal phrases
        cleaned = re.sub(r"\s+(tomorrow|today|next\s+\w+|this\s+\w+)$", "", cleaned).strip()

        prospects = self.db.get_prospects(search_query=cleaned, limit=3)
        if not prospects:
            return CopilotResponse(message=f"No prospect found matching '{cleaned}'.")

        if prospects[0].id is None:
            return CopilotResponse(message=f"No prospect found matching '{cleaned}'.")
        briefing = self.demo_briefing(prospects[0].id)
        return CopilotResponse(message=briefing)

    def _decay_report(self) -> CopilotResponse:
        """Generate decay/problems report."""
        from src.engine.intervention import InterventionEngine

        engine = InterventionEngine(self.db)
        report = engine.detect_decay()

        if report.total_issues == 0:
            return CopilotResponse(message="Pipeline looks clean. No decay detected.")

        lines = [f"Pipeline Health: {report.total_issues} issues found\n"]

        if report.overdue_followups:
            lines.append(f"Overdue follow-ups ({len(report.overdue_followups)}):")
            for item in report.overdue_followups[:5]:
                lines.append(f"  {item.prospect_name} ({item.company_name}): {item.description}")
            if len(report.overdue_followups) > 5:
                lines.append(f"  ... and {len(report.overdue_followups) - 5} more")
            lines.append("")

        if report.stale_engaged:
            lines.append(f"Stale engaged ({len(report.stale_engaged)}):")
            for item in report.stale_engaged[:5]:
                lines.append(f"  {item.prospect_name} ({item.company_name}): {item.description}")
            if len(report.stale_engaged) > 5:
                lines.append(f"  ... and {len(report.stale_engaged) - 5} more")
            lines.append("")

        if report.unworked:
            lines.append(f"Unworked cards ({len(report.unworked)}):")
            for item in report.unworked[:5]:
                lines.append(f"  {item.prospect_name} ({item.company_name}): {item.description}")
            if len(report.unworked) > 5:
                lines.append(f"  ... and {len(report.unworked) - 5} more")
            lines.append("")

        if report.low_confidence_high_score:
            lines.append(f"Data quality ({len(report.low_confidence_high_score)}):")
            for item in report.low_confidence_high_score[:3]:
                lines.append(f"  {item.prospect_name}: {item.description}")

        return CopilotResponse(message="\n".join(lines))

    def _learning_report(self) -> CopilotResponse:
        """Generate learning/patterns report."""
        from src.engine.learning import LearningEngine

        engine = LearningEngine(self.db)
        insights = engine.analyze_outcomes()

        lines = []

        if insights.win_rate is not None:
            lines.append(f"Win rate: {round(insights.win_rate * 100)}%")
        if insights.avg_cycle_days is not None:
            lines.append(f"Average deal cycle: {round(insights.avg_cycle_days)} days")
        lines.append("")

        if insights.win_patterns:
            lines.append("What's winning deals:")
            for wp in insights.win_patterns[:5]:
                lines.append(f"  {wp.pattern} ({wp.count} deals)")
            lines.append("")

        if insights.loss_patterns:
            lines.append("What's losing deals:")
            for lp in insights.loss_patterns[:5]:
                comp_str = f" [vs {lp.competitor}]" if lp.competitor else ""
                lines.append(f"  {lp.pattern} ({lp.count} deals){comp_str}")
            lines.append("")

        if insights.top_competitors:
            lines.append("Top competitors:")
            for comp, count in insights.top_competitors:
                lines.append(f"  {comp}: {count} losses")

        if not lines or all(l == "" for l in lines):
            return CopilotResponse(
                message="No closed deals yet to analyze. Patterns emerge after your first few wins and losses."
            )

        return CopilotResponse(message="\n".join(lines))

    def _ai_response(self, question: str) -> CopilotResponse:
        """Use Claude API for open-ended question answering."""
        try:
            client = self._get_client()
        except (RuntimeError, ImportError) as e:
            return CopilotResponse(message=f"AI not available: {e}")

        # Build context for the AI
        context = self.pipeline_summary()

        prompt = (
            "You are Anne, the AI sales assistant for Jeff Soderstrom at Nexys LLC. "
            "Jeff sells lending technology to mortgage companies. "
            "You are conversational, direct, and strategic. Keep responses concise.\n\n"
            f"Current pipeline state:\n{context}\n\n"
            f"Jeff asks: {question}\n\n"
            "Answer strategically and concisely."
        )

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            self._track_usage(
                "copilot", CLAUDE_MODEL,
                response.usage.input_tokens, response.usage.output_tokens,
            )
            return CopilotResponse(message=text, tokens_used=tokens)
        except Exception as e:
            logger.error(
                "Copilot AI call failed",
                extra={"context": {"error": str(e)}},
            )
            return CopilotResponse(
                message=f"AI response failed: {e}. Try a specific query instead."
            )

    # =========================================================================
    # UTILITY
    # =========================================================================

    def _parse_date(self, text: str) -> Optional[datetime]:
        """Parse a date from natural language or ISO format."""
        text = text.strip().lower()
        today = date.today()

        # ISO format
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        # YYYY-MM-DD
        try:
            d = date.fromisoformat(text)
            return datetime(d.year, d.month, d.day, 9, 0, 0)
        except ValueError:
            pass

        # Relative dates
        if text == "today":
            return datetime(today.year, today.month, today.day, 9, 0, 0)
        if text == "tomorrow":
            d = today + timedelta(days=1)
            return datetime(d.year, d.month, d.day, 9, 0, 0)

        # "next [day]"
        day_names = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        next_match = re.match(r"next\s+(\w+)", text)
        if next_match:
            day_name = next_match.group(1)
            if day_name in day_names:
                target_day = day_names[day_name]
                days_ahead = target_day - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                d = today + timedelta(days=days_ahead)
                return datetime(d.year, d.month, d.day, 9, 0, 0)

        # "in X days"
        in_days_match = re.match(r"in\s+(\d+)\s+days?", text)
        if in_days_match:
            d = today + timedelta(days=int(in_days_match.group(1)))
            return datetime(d.year, d.month, d.day, 9, 0, 0)

        return None

    def _parse_month(self, text: str) -> Optional[str]:
        """Parse a month string into YYYY-MM format."""
        text = text.strip().lower()
        today = date.today()

        # Already YYYY-MM format
        if re.match(r"^\d{4}-\d{2}$", text):
            return text

        month_names = {
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }

        # "March" or "March 2025"
        parts = text.split()
        if parts and parts[0] in month_names:
            month_num = month_names[parts[0]]
            if len(parts) > 1:
                try:
                    year = int(parts[1])
                    return f"{year}-{month_num:02d}"
                except ValueError:
                    pass
            # Default year: if month is in the past, assume next year
            year = today.year
            if month_num < today.month:
                year += 1
            return f"{year}-{month_num:02d}"

        return None
