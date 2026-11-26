import pytest

from yt_intel_mcp.errors import InvalidInput
from yt_intel_mcp.ids import ChannelRef, parse_channel_ref, parse_video_id

VID = "dQw4w9WgXcQ"
CID = "UC" + "a" * 20 + "AA"


@pytest.mark.parametrize(
    "value",
    [
        VID,
        f"https://www.youtube.com/watch?v={VID}",
        f"https://youtube.com/watch?v={VID}&t=42s&list=PL123",
        f"https://m.youtube.com/watch?feature=share&v={VID}",
        f"www.youtube.com/watch?v={VID}",
        f"https://www.youtube.com/shorts/{VID}",
        f"https://youtu.be/{VID}",
        f"https://youtu.be/{VID}?si=abc",
        f"https://www.youtube.com/embed/{VID}",
        f"https://www.youtube-nocookie.com/embed/{VID}",
        f"  {VID}  ",
    ],
)
def test_video_url_forms(value: str) -> None:
    assert parse_video_id(value) == VID


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "short",
        "dQw4w9WgXcQX",  # 12 chars
        "dQw4w9WgX!Q",
        "https://vimeo.com/123456789",
        "https://www.youtube.com/watch?v=tooShort",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/playlist?list=PL123",
        "javascript:alert(1)",
        "https://evil.example/watch?v=dQw4w9WgXcQ",
        "x" * 5000,
    ],
)
def test_malformed_video_ids(value: str) -> None:
    with pytest.raises(InvalidInput) as err:
        parse_video_id(value)
    assert err.value.next_step


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (CID, ChannelRef("id", CID)),
        (f"https://www.youtube.com/channel/{CID}", ChannelRef("id", CID)),
        ("@datadojo", ChannelRef("handle", "@datadojo")),
        ("https://www.youtube.com/@datadojo", ChannelRef("handle", "@datadojo")),
        ("https://www.youtube.com/@datadojo/videos", ChannelRef("handle", "@datadojo")),
        ("https://www.youtube.com/user/datadojo", ChannelRef("username", "datadojo")),
        ("https://www.youtube.com/c/breadlab", ChannelRef("custom", "breadlab")),
    ],
)
def test_channel_forms(value: str, expected: ChannelRef) -> None:
    assert parse_channel_ref(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "datadojo",
        "@x",
        "UCshort",
        "https://www.youtube.com/channel/notanid",
        "https://example.com/@datadojo",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ],
)
def test_malformed_channel_refs(value: str) -> None:
    with pytest.raises(InvalidInput):
        parse_channel_ref(value)
