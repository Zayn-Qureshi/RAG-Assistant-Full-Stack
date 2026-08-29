# Security Audit & Hardening Notes

Written for anyone (including future-you) evaluating this system before an
organizational deployment. Organized by what's fixed, what's a known
accepted limitation, and what MUST change before real production use.

## Fixed in this pass

- **Dependency versions pinned** (`requirements.txt`) to patched-minimum
  releases, closing known CVEs current as of Aug 2026:
  - `fastapi>=0.115.8` — fixes CVE-2026-2978 (critical RCE, CVSS 9.8)
  - `python-multipart>=0.0.26` — fixes CVE-2026-40347 (DoS) and
    CVE-2026-24486 (path traversal via non-default config)
  - Run `pip install pip-audit && pip-audit` periodically — new CVEs are
    published constantly; pinned versions here will go stale.
- **CORS locked down** — was `allow_origins=["*"]` (any website could call
  your API from a user's browser). Now reads from `ALLOWED_ORIGINS` in
  `.env`, defaults to only your local frontend.
- **Path traversal in file upload fixed** — `file.filename` is
  client-controlled; a malicious filename like `../../etc/passwd` could
  previously write outside the intended folder. Now sanitized + validated.
- **File content validation added** — previously only checked the file
  extension, which is trivially spoofed (rename any file to `.pdf`). Now
  checks the actual file signature (magic bytes) for PDFs.
- **Constant-time API key comparison** — was a plain `!=` check, which
  leaks timing information; now uses `hmac.compare_digest`.
- **Auth-disabled state now logged loudly** at startup instead of silently
  allowed — if `APP_API_KEY` isn't set, you'll see a clear warning.

## Known limitations — accepted for personal/portfolio scale, NOT acceptable as-is for an organization

Read this section before deploying anywhere beyond your own machine.

### Authentication
Single shared API key — no per-user identity, no per-user revocation, no
audit trail of *who* asked *what*. **For an organization: implement
per-user API keys or OAuth/JWT with a real users table before any
multi-person deployment.**

### Guardrails
The prompt-injection filter (`guardrails.py`) is regex pattern-matching —
it catches obvious, undisguised attempts and will miss anything reworded
or written in another language. **This is not a real security boundary,
it's a basic first filter.** For an organization handling untrusted input
at scale, add a proper moderation/classification model layer.

### Rate limiting & semantic cache
Both are in-memory, per-process. They reset on restart and don't share
state across multiple instances. **For an organization running more than
one instance (which you would, for any real availability), back both
with Redis** — otherwise rate limits and cache are trivially bypassed by
hitting a different instance, and provide a false sense of protection.

### Data residency & third-party exposure
Every query and every uploaded document's content is sent to **Gemini**
(Google) and stored as vectors in **Pinecone** (a third party). For an
organization, before processing real internal documents:
- Review both providers' data processing agreements and data residency
  terms — confirm they meet your organization's compliance requirements
  (GDPR, industry-specific regulations, etc.)
- Confirm whether either provider trains on submitted data by default,
  and disable that if so
- OCR (Tesseract) is intentionally local per an earlier decision — but
  the underlying document is embedded and sent to Gemini afterward
  regardless. Local OCR alone does not make this a fully local pipeline.

### Query/document logging
Full query text is logged to SQLite (`query_logs` table) and a CSV
(`token_usage.csv`), unredacted. If an internal user asks something
containing sensitive information, it's now sitting in a local database
and a plaintext file with no expiry. **For an organization: define a
retention policy, and consider redacting or hashing logged query text
if it may contain sensitive information.**

### Transport security
Everything here runs over plain HTTP on localhost. **For any real
deployment: put this behind HTTPS/TLS** (a reverse proxy like nginx or
Caddy handling TLS termination is the standard approach) — API keys and
document content would otherwise travel in plaintext over the network.

### Container security
The `Dockerfile` runs as root by default (no `USER` directive). **For
production: add a non-root user** so a container compromise doesn't
grant root inside the container.

### SQLite
Fine for single-instance use; **not safe for concurrent multi-writer
access at organization scale** — would need to migrate to Postgres for
any real multi-instance deployment.

## Recommended next steps, in priority order, before organizational use

1. Add per-user authentication (replace the shared API key)
2. Put the API behind HTTPS via a reverse proxy
3. Move rate limiting + semantic cache to Redis
4. Add a non-root user to the Dockerfile
5. Review Gemini/Pinecone data processing agreements for your org's
   compliance needs
6. Define and implement a log retention/redaction policy
7. Set up `pip-audit` (or Dependabot/Snyk) to run on a schedule, not
   just once at pinning time — dependency CVEs are discovered
   continuously
8. Migrate SQLite to Postgres if running more than one instance