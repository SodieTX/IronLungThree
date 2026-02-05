"""Email recall — the "Oh Shit" button.

Attempts to recall/retract a sent email via Graph API.

Limitations:
    - Only works for internal recipients (same Microsoft 365 org)
    - External recipients cannot have emails recalled via API
    - Even internal recall is best-effort (may fail if already read)

For external recipients, the fallback is to send a "please disregard"
follow-up email.

Usage:
    from src.engine.email_recall import attempt_recall

    result = attempt_recall(outlook, message_id)
"""

from dataclasses import dataclass
from typing import Optional

from src.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RecallResult:
    """Result of a recall attempt.

    Attributes:
        success: Whether the recall action was executed
        method: "deleted" (removed from sent), "follow_up" (sent apology), or "failed"
        message: Human-readable description of what happened
    """

    success: bool
    method: str = ""
    message: str = ""


def attempt_recall(
    outlook: object,
    message_id: str,
    send_follow_up: bool = True,
    follow_up_text: Optional[str] = None,
) -> RecallResult:
    """Attempt to recall a sent email.

    Strategy:
        1. Try to delete the message from Sent Items
        2. Optionally send a "please disregard" follow-up

    Note: Microsoft Graph API does not support true message recall
    for external recipients. This is a best-effort approach.

    Args:
        outlook: OutlookClient instance
        message_id: ID of the sent message to recall
        send_follow_up: If True, send a "please disregard" follow-up
        follow_up_text: Custom follow-up text (default provided)

    Returns:
        RecallResult with outcome details
    """
    if not message_id:
        return RecallResult(
            success=False,
            method="failed",
            message="No message ID provided",
        )

    # Step 1: Try to delete the sent message
    deleted = _delete_sent_message(outlook, message_id)

    # Step 2: Send follow-up if requested
    if send_follow_up:
        original = _get_original_message(outlook, message_id)
        if original:
            to_address = original.get("to", "")
            subject = original.get("subject", "")
            if to_address:
                body = follow_up_text or (
                    "I apologize — please disregard my previous email. "
                    "It was sent in error."
                )
                try:
                    outlook.send_email(  # type: ignore[union-attr]
                        to=to_address,
                        subject=f"Please disregard: {subject}",
                        body=body,
                    )
                    logger.info(
                        f"Recall follow-up sent to {to_address}",
                        extra={"context": {"message_id": message_id}},
                    )
                    return RecallResult(
                        success=True,
                        method="follow_up",
                        message=(
                            f"Sent 'please disregard' to {to_address}. "
                            "Original message deleted from Sent Items."
                            if deleted else
                            f"Sent 'please disregard' to {to_address}."
                        ),
                    )
                except Exception as e:
                    logger.error(f"Failed to send recall follow-up: {e}")

    if deleted:
        return RecallResult(
            success=True,
            method="deleted",
            message="Message deleted from Sent Items. "
            "Recipient may still have the original.",
        )

    return RecallResult(
        success=False,
        method="failed",
        message="Could not recall message. "
        "The recipient may still have the original.",
    )


def _delete_sent_message(outlook: object, message_id: str) -> bool:
    """Try to delete the message from Sent Items.

    Args:
        outlook: OutlookClient
        message_id: Message ID

    Returns:
        True if deletion succeeded
    """
    try:
        response = outlook._graph_request(  # type: ignore[union-attr]
            "DELETE",
            f"/users/{outlook._user_email}/messages/{message_id}",  # type: ignore[union-attr]
        )
        if response.status_code == 204:
            logger.info(f"Deleted message {message_id} from Sent Items")
            return True
        else:
            logger.warning(
                f"Failed to delete message {message_id}: {response.status_code}"
            )
            return False
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        return False


def _get_original_message(
    outlook: object, message_id: str
) -> Optional[dict[str, str]]:
    """Retrieve original message details for follow-up.

    Args:
        outlook: OutlookClient
        message_id: Message ID

    Returns:
        Dict with 'to' and 'subject', or None if not found
    """
    try:
        response = outlook._graph_request(  # type: ignore[union-attr]
            "GET",
            f"/users/{outlook._user_email}/messages/{message_id}",  # type: ignore[union-attr]
            params={"$select": "subject,toRecipients"},
        )
        if response.status_code == 200:
            data = response.json()
            to_recipients = data.get("toRecipients", [])
            to_addr = ""
            if to_recipients:
                to_addr = to_recipients[0].get("emailAddress", {}).get("address", "")
            return {
                "to": to_addr,
                "subject": data.get("subject", ""),
            }
    except Exception as e:
        logger.error(f"Error reading original message: {e}")

    return None
