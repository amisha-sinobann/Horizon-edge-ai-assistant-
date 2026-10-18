"""Validation helpers for untrusted URLs and downloaded PDF content."""

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    """Raised when a URL could target an unsafe or non-public destination."""


def validate_public_https_url(url: str) -> None:
    """Reject non-HTTPS URLs and hosts resolving to private or reserved IPs."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeUrlError("only credential-free HTTPS URLs are allowed")
    try:
        addresses = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise UnsafeUrlError("URL host could not be resolved") from exc
    if not addresses or any(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
        for address in addresses
    ):
        raise UnsafeUrlError("URL host must resolve only to public IP addresses")


def validate_pdf_response(content_type: str, first_bytes: bytes, size: int, max_bytes: int) -> None:
    """Validate a downloaded response before it is persisted and parsed."""
    if size > max_bytes:
        raise ValueError("PDF exceeds configured maximum size")
    if not first_bytes.startswith(b"%PDF-"):
        raise ValueError("download is not a PDF")
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type and normalized_type not in {"application/pdf", "binary/octet-stream"}:
        raise ValueError("download content type is not a PDF")
