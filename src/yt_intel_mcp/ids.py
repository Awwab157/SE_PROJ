"""Parsing of video and channel URLs/IDs (FR-1.1, FR-2.1, FR-2.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

from yt_intel_mcp.errors import InvalidInput

MAX_INPUT_LENGTH = 2048

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
HANDLE_RE = re.compile(r"^@[\w.\-·]{3,30}$", re.UNICODE)
NAME_RE = re.compile(r"^[\w.\-]{1,100}$", re.UNICODE)

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}
SHORT_HOSTS = {"youtu.be", "www.youtu.be"}

VIDEO_HINT = "Use a YouTube video URL (watch, /shorts/, youtu.be, /embed/) or an 11-character video ID."
CHANNEL_HINT = "Use a channel ID (UC...), an @handle, or a channel URL (/channel/, /@handle, /user/, /c/)."


def _prepare(value: str, hint: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput("The value is empty.", hint)
    value = value.strip()
    if len(value) > MAX_INPUT_LENGTH:
        raise InvalidInput("The value is too long to be a YouTube URL or ID.", hint)
    return value


def _as_url(value: str):
    url = value if "://" in value else "https://" + value
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    return parsed


def parse_video_id(value: str) -> str:
    value = _prepare(value, VIDEO_HINT)
    if VIDEO_ID_RE.match(value):
        return value
    parsed = _as_url(value)
    candidate: str | None = None
    if parsed is not None and parsed.hostname:
        host = parsed.hostname.lower()
        parts = [p for p in parsed.path.split("/") if p]
        if host in SHORT_HOSTS and parts:
            candidate = parts[0]
        elif host in YOUTUBE_HOSTS:
            if parsed.path.rstrip("/") == "/watch":
                candidate = (parse_qs(parsed.query).get("v") or [None])[0]
            elif len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                candidate = parts[1]
    if candidate and VIDEO_ID_RE.match(candidate):
        return candidate
    raise InvalidInput("This is not a recognised YouTube video URL or video ID.", VIDEO_HINT)


@dataclass(frozen=True)
class ChannelRef:
    kind: Literal["id", "handle", "username", "custom"]
    value: str


def parse_channel_ref(value: str) -> ChannelRef:
    value = _prepare(value, CHANNEL_HINT)
    if CHANNEL_ID_RE.match(value):
        return ChannelRef("id", value)
    if value.startswith("@"):
        if HANDLE_RE.match(value):
            return ChannelRef("handle", value)
        raise InvalidInput("This is not a valid YouTube @handle.", CHANNEL_HINT)
    parsed = _as_url(value)
    if parsed is not None and parsed.hostname and parsed.hostname.lower() in YOUTUBE_HOSTS:
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        if parts:
            head = parts[0]
            if head.startswith("@") and HANDLE_RE.match(head):
                return ChannelRef("handle", head)
            if len(parts) >= 2:
                name = parts[1]
                if head == "channel" and CHANNEL_ID_RE.match(name):
                    return ChannelRef("id", name)
                if head == "user" and NAME_RE.match(name):
                    return ChannelRef("username", name)
                if head == "c" and NAME_RE.match(name):
                    return ChannelRef("custom", name)
    raise InvalidInput("This is not a recognised YouTube channel URL, handle or channel ID.", CHANNEL_HINT)


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def channel_url(channel_id: str) -> str:
    return f"https://www.youtube.com/channel/{channel_id}"


def playlist_url(playlist_id: str) -> str:
    return f"https://www.youtube.com/playlist?list={playlist_id}"
