from __future__ import annotations

import pytest

from app.utils.timecode import filename_stamp, format_timecode, parse_timecode


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("0", 0),
        ("45", 45),
        ("1:30", 90),
        ("01:30", 90),
        ("1:02:03", 3723),
        ("08:00:00", 28800),
        ("  00:10:00 ", 600),
        ("90:00", 5400),  # minutes > 59 acceptées en tête (« 90:00 » = 1 h 30)
    ],
)
def test_parse_timecode_accepts_common_forms(text, seconds):
    assert parse_timecode(text) == seconds


@pytest.mark.parametrize("text", ["", "abc", "1:2:3:4", "1:75", "1:00:61", "-5", "1:-2", "1,5", "1h30"])
def test_parse_timecode_rejects_garbage(text):
    with pytest.raises(ValueError, match="hh:mm:ss"):
        parse_timecode(text)


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "00:00:00"), (59, "00:00:59"), (3723, "01:02:03"), (28800, "08:00:00"), (360000, "100:00:00")],
)
def test_format_timecode(seconds, text):
    assert format_timecode(seconds) == text


def test_format_then_parse_roundtrip():
    for value in (0, 1, 61, 3599, 3600, 86399):
        assert parse_timecode(format_timecode(value)) == value


def test_filename_stamp_has_no_windows_forbidden_characters():
    stamp = filename_stamp(300, 3723)
    assert stamp == "00h05m00s-01h02m03s"
    assert not set(stamp) & set('<>:"/\\|?*')
