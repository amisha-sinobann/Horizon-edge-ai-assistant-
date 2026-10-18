# HorizonForge security controls

This folder contains security-sensitive URL and file validation shared by the
agents.

- Outbound paper and DOI requests require credential-free HTTPS URLs.
- DNS results must be public, non-reserved addresses; loopback, private,
  link-local, multicast, and unspecified addresses are rejected.
- Redirects are not followed automatically.
- PDF downloads are streamed, size-limited, checked for a PDF signature, and
  checked for an appropriate content type before parsing.
- API keys remain environment-only and are excluded by `.gitignore`.

These controls reduce SSRF and resource-exhaustion risk but do not replace
network egress controls, dependency updates, or production authentication.
