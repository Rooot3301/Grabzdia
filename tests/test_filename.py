import pytest

from app.utils.filename import is_within_directory, sanitize_filename, validate_output_template


def test_sanitizes_windows_names():
    assert sanitize_filename('bad<>:"/\\|?* ') == "bad_________"
    assert sanitize_filename("CON.txt") == "_CON.txt"

def test_template_cannot_escape():
    with pytest.raises(ValueError): validate_output_template("../%(title)s.%(ext)s")
    assert validate_output_template("%(title)s [%(id)s].%(ext)s")

def test_path_confinement(tmp_path):
    assert is_within_directory(tmp_path, tmp_path / "safe.mp4")
    assert not is_within_directory(tmp_path, tmp_path.parent / "escape.mp4")
