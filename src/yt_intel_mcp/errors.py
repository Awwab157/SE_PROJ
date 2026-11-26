"""Structured errors. Every error carries a code, a cause and a next step (UI-3).

Messages are written by this module, never copied from library exceptions, so tokens and stack
traces cannot leak into tool results.
"""

from __future__ import annotations

from typing import Any


class YTIntelError(Exception):
    code = "internal_error"
    default_next_step = "Retry the request. If it keeps failing, check the server log (it is redacted)."

    def __init__(self, cause: str, next_step: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(cause)
        self.cause = cause
        self.next_step = next_step or self.default_next_step
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "cause": self.cause, "next_step": self.next_step, "details": self.details}


class InternalError(YTIntelError):
    code = "internal_error"


class InvalidInput(YTIntelError):
    code = "invalid_input"
    default_next_step = "Correct the input described in the cause and call the tool again."


# --- Provider errors (mapped from YouTube API responses in providers/live.py) ---------------------


class NotFound(YTIntelError):
    code = "not_found"
    default_next_step = "Check the URL or ID. The item may be private, deleted or terminated."


class Forbidden(YTIntelError):
    code = "forbidden"
    default_next_step = "The authorised account cannot access this item. Check its privacy settings."


class QuotaExceeded(YTIntelError):
    code = "quota_exceeded"
    default_next_step = "The YouTube API daily quota is used up. Try again after midnight Pacific Time."


class RateLimited(YTIntelError):
    code = "rate_limited"
    default_next_step = "YouTube is rate limiting requests. Wait a minute and try again."


class YoutubeSignupRequired(YTIntelError):
    code = "youtube_signup_required"
    default_next_step = (
        "This Google account needs a YouTube channel before it can create playlists. "
        "Create one at https://www.youtube.com/create_channel and try again."
    )


class InvalidGrant(YTIntelError):
    code = "reauthorization_required"
    default_next_step = (
        "Call start_authorization to sign in again. Tokens for apps in Google 'Testing' mode expire after 7 days."
    )


class Transient(YTIntelError):
    code = "transient_error"
    default_next_step = "A temporary YouTube or network error occurred. Try again shortly."


# --- Auth --------------------------------------------------------------------------------------------


class AuthorizationRequired(YTIntelError):
    code = "authorization_required"
    default_next_step = "Call start_authorization to connect a YouTube account (read-only access)."


class WriteScopeRequired(YTIntelError):
    code = "write_scope_required"
    default_next_step = (
        "Playlist creation needs the 'youtube' scope. Approve the extra permission when the browser "
        "opens, then call create_playlist again."
    )


# --- Quota -------------------------------------------------------------------------------------------


class QuotaBudgetExceeded(YTIntelError):
    code = "quota_budget_exceeded"
    default_next_step = "Reduce the request size (for example a lower limit) or wait for the daily reset."


# --- Proposals and approval -----------------------------------------------------------------------


class ProposalNotFound(YTIntelError):
    code = "proposal_not_found"
    default_next_step = "Call propose_playlist to create a new proposal."


class ProposalExpired(YTIntelError):
    code = "proposal_expired"
    default_next_step = "Proposals expire after 10 minutes. Call propose_playlist again."


class ProposalDeclined(YTIntelError):
    code = "proposal_declined"
    default_next_step = "This proposal was declined. Call propose_playlist to start again."


class ProposalInProgress(YTIntelError):
    code = "proposal_in_progress"
    default_next_step = "Playlist creation for this proposal is already running. Try again in a minute."


class ConfirmationInvalid(YTIntelError):
    code = "confirmation_invalid"
    default_next_step = (
        "Ask the user to read the code shown on the local approval page on their computer. Never guess it."
    )


class ApprovalUnavailable(YTIntelError):
    code = "approval_unavailable"
    default_next_step = (
        "Use an MCP client that supports elicitation, or run the server on a desktop where a local "
        "approval page can open in the browser. No playlist was created."
    )
