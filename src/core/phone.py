"""Phone number normalization utility.

Single source of truth for phone formatting used by intake, CSV importer,
database lookups, and Bria dialer.
"""


def normalize_phone(phone: str) -> str:
    """Normalize phone to 10-digit US format.

    Strips non-digits, then removes leading '1' country code
    if the result is 11 digits starting with '1'.

    Args:
        phone: Phone number in any format

    Returns:
        10-digit US phone (e.g., "7135551234") or raw digits for non-US

    Examples:
        >>> normalize_phone("(713) 555-1234")
        '7135551234'
        >>> normalize_phone("+1-713-555-1234")
        '7135551234'
        >>> normalize_phone("7135551234")
        '7135551234'
    """
    digits = "".join(c for c in phone if c.isdigit())
    # Strip US country code prefix
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits
