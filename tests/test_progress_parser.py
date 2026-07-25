from app.parsers.progress_parser import parse_progress


def test_progress_line():
    value = parse_progress("GZPROGRESS:64.2%|10MiB|20MiB|2MiB/s|00:05")
    assert value and value.percent == 64.2 and value.eta == "00:05"

def test_ignores_noise(): assert parse_progress("[download] noise") is None

