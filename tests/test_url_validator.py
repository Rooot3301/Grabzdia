import pytest

from app.exceptions import InvalidUrlError
from app.utils.url_validator import validate_media_url


@pytest.mark.parametrize("url", ["https://example.com/video", "http://example.org/a?q=1"])
def test_accepts_http_urls(url): assert validate_media_url(url) == url

@pytest.mark.parametrize("url", ["", "ftp://example.com/a", "javascript:alert(1)", "https://user:pass@example.com", "http://127.0.0.1/a"])
def test_rejects_unsafe_urls(url):
    with pytest.raises(InvalidUrlError): validate_media_url(url)

