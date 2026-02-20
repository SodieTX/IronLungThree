"""Style learner for Jeff's email voice.

Uses curated examples (10-15 of Jeff's best emails) to
generate emails in his voice.
"""

from pathlib import Path

from src.core.logging import get_logger

logger = get_logger(__name__)

STYLE_DIR = Path(__file__).parent.parent.parent / "data" / "style_examples"


def load_examples() -> list[str]:
    """Load Jeff's email examples from data/style_examples/.

    Reads all .txt files from the style directory, sorted by name.
    Each file should contain one email example.

    Returns:
        List of email text strings.
    """
    if not STYLE_DIR.exists():
        logger.info(
            "Style examples directory not found", extra={"context": {"path": str(STYLE_DIR)}}
        )
        return []

    examples: list[str] = []
    for path in sorted(STYLE_DIR.glob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                examples.append(text)
        except OSError as e:
            logger.warning(f"Failed to read style example {path.name}: {e}")

    logger.info(f"Loaded {len(examples)} style examples")
    return examples


def get_style_prompt() -> str:
    """Generate style guidance for email drafting.

    Returns a prompt section containing loaded examples and style notes.
    If no examples exist, returns a minimal guidance string.
    """
    examples = load_examples()
    if not examples:
        return (
            "Write in a professional but conversational tone. "
            "Be direct and concise. No corporate buzzwords."
        )

    style = analyze_style(examples)

    parts = [
        "Write emails in Jeff's voice. Here are examples of his style:\n",
    ]
    for i, ex in enumerate(examples, 1):
        parts.append(f"--- Example {i} ---\n{ex}\n")

    parts.append("--- Style notes ---")
    parts.append(f"Average length: ~{style['avg_length']} words")
    parts.append(f"Tone: {style['tone']}")
    if style["common_openers"]:
        parts.append(f"Common openers: {', '.join(style['common_openers'])}")
    parts.append("Match this voice exactly. No corporate fluff.")

    return "\n".join(parts)


def analyze_style(examples: list[str]) -> dict:
    """Analyze style characteristics from examples.

    Returns dict with avg_length, tone, common_openers.
    """
    if not examples:
        return {"avg_length": 0, "tone": "professional", "common_openers": []}

    word_counts = [len(ex.split()) for ex in examples]
    avg_length = sum(word_counts) // len(word_counts)

    # Detect tone from word choice
    casual_markers = ["hey", "hi,", "hi!", "hi\n", "thanks", "cheers", "!", "appreciate"]
    formal_markers = ["dear", "regards", "sincerely", "pursuant", "herewith"]

    casual_count = sum(1 for ex in examples for marker in casual_markers if marker in ex.lower())
    formal_count = sum(1 for ex in examples for marker in formal_markers if marker in ex.lower())

    if casual_count > formal_count:
        tone = "conversational and direct"
    elif formal_count > casual_count:
        tone = "professional and formal"
    else:
        tone = "professional but approachable"

    # Extract common first lines
    openers: list[str] = []
    for ex in examples:
        first_line = ex.split("\n")[0].strip()
        if first_line and len(first_line) < 80:
            openers.append(first_line)

    # Deduplicate similar openers (keep first 3 unique-ish)
    seen: set[str] = set()
    unique_openers: list[str] = []
    for opener in openers:
        key = opener.lower()[:20]
        if key not in seen:
            seen.add(key)
            unique_openers.append(opener)
        if len(unique_openers) >= 3:
            break

    return {
        "avg_length": avg_length,
        "tone": tone,
        "common_openers": unique_openers,
    }
