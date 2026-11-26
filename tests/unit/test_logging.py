import logging

from yt_intel_mcp.logging_utils import RedactingFormatter, configure_logging, log_event, redact

FAKE_ACCESS = "ya29.a0AfB_fakeTOKENvalue-1234567890"
FAKE_REFRESH = "1//0gFAKErefreshTOKEN_abcdefghijkl"


def test_redact_tokens_emails_ids() -> None:
    text = (
        f"auth {FAKE_ACCESS} refresh {FAKE_REFRESH} Bearer abc.def.ghi "
        '{"access_token": "secret1", "refresh_token": "secret2"} user person@example.com '
        "channel UCSynthDataDojo0000000AA"
    )
    out = redact(text)
    for secret in (
        FAKE_ACCESS,
        FAKE_REFRESH,
        "abc.def.ghi",
        "secret1",
        "secret2",
        "person@example.com",
        "UCSynthDataDojo0000000AA",
    ):
        assert secret not in out


def test_log_event_drops_sensitive_fields_and_redacts(caplog) -> None:
    logger = configure_logging()
    logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="yt_intel_mcp"):
            log_event(
                "x",
                title="My Secret Video",
                channel_title="Somebody",
                query="private query",
                tool="find_similar_videos",
                note=f"token={FAKE_ACCESS} mail=person@example.com",
            )
        formatted = RedactingFormatter("%(message)s").format(caplog.records[-1])
    finally:
        logger.propagate = False
    assert "My Secret Video" not in formatted
    assert "Somebody" not in formatted
    assert "private query" not in formatted
    assert FAKE_ACCESS not in formatted
    assert "person@example.com" not in formatted
    assert "tool=find_similar_videos" in formatted


def test_formatter_drops_tracebacks() -> None:
    try:
        raise ValueError(f"boom {FAKE_ACCESS}")
    except ValueError:
        import sys

        record = logging.LogRecord("yt_intel_mcp", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    out = RedactingFormatter("%(message)s").format(record)
    assert "Traceback" not in out
    assert FAKE_ACCESS not in out


def test_tool_timer_logs_name_duration_and_outcome(caplog) -> None:
    from yt_intel_mcp.logging_utils import tool_timer

    logger = configure_logging()
    logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="yt_intel_mcp"):
            with tool_timer("find_similar_videos") as info:
                info["outcome"] = "error"
                info["error"] = "not_found"
    finally:
        logger.propagate = False
    message = caplog.records[-1].getMessage()
    assert "tool=find_similar_videos" in message
    assert "duration_ms=" in message
    assert "outcome=error" in message and "error=not_found" in message
