# SECURITY.md — Threat Model & Jev-Enforced Controls

**Threat model:** prompt-injected domain docs, hallucinated/jailbroken eval outputs, PII in datasets, leaked credentials in commits, vulnerable pinned dependencies, dashboard session hijack.

**Jev-enforced controls**
- All inputs/outputs pass `SecurityLayer` scrubbing (regex + presidio NER patterns: email, SSN, credit-card, phone) before processing or publication.
- GitHub auto-push uses a scoped PAT from env `GITHUB_TOKEN` (repo scope only) — never hardcoded, never logged.
- Audit logs are structured JSON, PII-scrubbed, append-only (`webapp/backend/state/audit.log`), viewable in the Security Center.
- Dependencies pinned in `requirements.txt`; Phase 5 runs `pip-audit` + `gitleaks` patterns on every commit and blocks on critical CVE/secrets.
- Dashboard: OAuth2 password flow with HMAC-signed tokens, RBAC (viewer/operator/admin), 1-hour session timeout, no raw-data export endpoints.

**Reporting:** email security@jev-harness.local with a redacted PoC. Response SLA: 72h triage. Do not open public issues for vulnerabilities.
