from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import re


MAX_RETRY_AFTER_SECONDS = 3600
DEFAULT_RETRY_AFTER_SECONDS = 60


def parse_retry_after(retry_after=None, reset_epoch=None, *, now=None):
    """Return a safe positive retry delay from Retry-After or reset headers.

    Retry-After may be delta-seconds or an HTTP-date. Delays are clamped to
    [1 second, 1 hour]. The GitHub primary-reset epoch is used as a fallback;
    malformed or absent values use a conservative one-minute delay.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    seconds = None
    value = str(retry_after or "").strip()
    if value:
        if re.fullmatch(r"-?\d+", value):
            try:
                seconds = int(value)
            except (ValueError, OverflowError):
                seconds = MAX_RETRY_AFTER_SECONDS
        else:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                seconds = math.ceil((retry_at - now).total_seconds())
            except (TypeError, ValueError, OverflowError):
                seconds = None

    if seconds is None:
        try:
            reset = int(str(reset_epoch).strip())
            seconds = math.ceil(reset - now.timestamp())
        except (TypeError, ValueError, OverflowError):
            seconds = DEFAULT_RETRY_AFTER_SECONDS

    return max(1, min(int(seconds), MAX_RETRY_AFTER_SECONDS))


def is_secondary_rate_limit_response(response):
    """Recognize GitHub's explicit secondary-limit body when headers omit it."""
    try:
        payload = response.json()
    except Exception:
        return False
    message = payload.get("message", "") if isinstance(payload, dict) else ""
    return isinstance(message, str) and "secondary rate limit" in message.lower()


class GitHubRateLimitExceeded(RuntimeError):
    """A safely classified upstream GitHub primary or secondary limit."""

    def __init__(self, retry_after=None):
        super().__init__("GitHub upstream rate limit exceeded")
        self.retry_after = max(
            1,
            min(int(retry_after or DEFAULT_RETRY_AFTER_SECONDS), MAX_RETRY_AFTER_SECONDS),
        )


class GitHubUpstreamBudgetExceeded(RuntimeError):
    """The shared GitHub API call budget is temporarily exhausted."""

    def __init__(self, retry_after):
        super().__init__("GitScope GitHub API budget exhausted")
        self.retry_after = max(1, min(int(retry_after), MAX_RETRY_AFTER_SECONDS))
