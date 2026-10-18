"""Tests for outbound URL and PDF validation."""

import pytest

from security.url_safety import UnsafeUrlError, validate_pdf_response, validate_public_https_url


def test_rejects_non_https():
    """HTTP URLs cannot be used for outbound paper requests."""
    with pytest.raises(UnsafeUrlError):
        validate_public_https_url("http://example.com/paper.pdf")


def test_rejects_credentials():
    """URLs containing embedded credentials are rejected."""
    with pytest.raises(UnsafeUrlError):
        validate_public_https_url("https://user:password@example.com/paper.pdf")


def test_rejects_non_pdf():
    """HTML or other content cannot reach the PDF parser."""
    with pytest.raises(ValueError):
        validate_pdf_response("text/html", b"<html>", 6, 100)


def test_accepts_pdf_signature():
    """A correctly signed, bounded PDF response is accepted."""
    validate_pdf_response("application/pdf", b"%PDF-1.7", 8, 100)
