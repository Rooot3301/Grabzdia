from __future__ import annotations

from app.parsers.error_parser import MAX_RAW, Diagnosis, diagnose


def test_recognises_private_video():
    result = diagnose(["ERROR: [youtube] abc: Private video. Sign in if you've been granted access"], 1)
    assert result.reason == "Vidéo privée"
    assert "propriétaire" in result.hint


def test_recognises_geo_restriction():
    result = diagnose(["ERROR: The uploader has not made this video available in your country"], 1)
    assert result.reason == "Bloquée dans votre pays"


def test_recognises_missing_format():
    result = diagnose(["ERROR: Requested format is not available"], 1)
    assert result.reason == "Format demandé indisponible"
    assert "Automatique" in result.hint


def test_recognises_rate_limiting():
    result = diagnose(["ERROR: Unable to download webpage: HTTP Error 429: Too Many Requests"], 1)
    assert result.reason == "Trop de requêtes"


def test_recognises_full_disk():
    result = diagnose(["ERROR: unable to write data: [Errno 28] No space left on device"], 1)
    assert result.reason == "Espace disque insuffisant"


def test_matching_is_case_insensitive():
    result = diagnose(["error: VIDEO UNAVAILABLE"], 1)
    assert result.reason == "Vidéo indisponible"


def test_specific_rule_wins_over_generic_one():
    """Une vidéo réservée aux membres renvoie aussi un 403 : le motif précis doit gagner."""
    lines = [
        "ERROR: This video is available to this channel's members on level: Soutien",
        "ERROR: unable to download video data: HTTP Error 403: Forbidden",
    ]
    assert diagnose(lines, 1).reason == "Réservée aux membres"


def test_unknown_error_falls_back_to_the_raw_error_line():
    lines = ["[youtube] Extracting URL", "ERROR: quelque chose d'inédit a mal tourné"]
    result = diagnose(lines, 1)
    assert result.reason == "quelque chose d'inédit a mal tourné"
    assert result.hint == ""


def test_falls_back_to_the_last_error_line_when_several():
    lines = ["ERROR: premier souci", "ERROR: dernier souci"]
    assert diagnose(lines, 1).reason == "dernier souci"


def test_without_any_error_line_reports_the_exit_code():
    result = diagnose(["[youtube] Extracting URL", "[download] Destination: a.mp4"], 3)
    assert "3" in result.reason
    assert result.hint == ""


def test_empty_output_still_reports_the_exit_code():
    assert "2" in diagnose([], 2).reason


def test_raw_keeps_the_output_and_is_capped():
    lines = ["x" * 500 for _ in range(20)]
    result = diagnose(lines, 1)
    assert len(result.raw) <= MAX_RAW


def test_diagnosis_is_immutable():
    result = diagnose(["ERROR: Video unavailable"], 1)
    assert isinstance(result, Diagnosis)
    try:
        result.reason = "autre"
    except Exception:
        return
    raise AssertionError("Diagnosis devrait être gelée")
