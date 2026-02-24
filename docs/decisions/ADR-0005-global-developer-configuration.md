# ADR-0005: Global Developer Configuration

> **Status:** Complete
> **Date:** 2025-12-06
> **Related Issue:** N/A (proactive infrastructure improvement)

---

## Executive Summary

Established a global configuration layer for consistent development experience across all Project Ike repositories. This includes GitHub authentication standardization, user-level Claude Code instructions, global permissions, and cross-repo ADR aggregation.

---

## Context

Working across multiple repos (ike-semantic-ops, ike-publisher, project-ike-private, data-systems-toolkit, resumator) created friction:

1. **GitHub authentication was unreliable** - Mix of SSH and HTTPS remotes, conflicting tokens (GITHUB_TOKEN env var vs gh CLI keyring), inconsistent auth failures
2. **No shared context for Claude Code** - Each session started fresh without understanding the system architecture
3. **Repeated permission approvals** - Common safe commands required approval in every session
4. **ADRs scattered across repos** - No unified view of architectural decisions

---

## Decision

### 1. GitHub Authentication: HTTPS + GITHUB_TOKEN Only

**Configuration:**
- Single Personal Access Token (Classic) stored in `~/.bashrc`
- All repos use HTTPS remotes (not SSH)
- `gh` CLI uses `GITHUB_TOKEN` env var as sole auth method
- Removed conflicting keyring OAuth token from `gh auth`

**Token Scopes:**
- `repo` - Full control of private repos
- `workflow` - Update GitHub Actions
- `read:org` - Read org membership
- `admin:repo_hook` - Webhook management

### 2. User-Level Claude Code Configuration

**~/.claude/CLAUDE.md** - Global instructions including:
- Project Ike architecture overview (system map, repo roles)
- GitHub auth rules
- Development standards (ruff, pytest, pydantic)
- ADR conventions
- Key domain concepts (Concept, Entity, Edge, Surface, Delivery)
- Security practices

**~/.claude/settings.json** - Global permissions auto-approving:
- Git/GitHub commands (`git`, `gh`)
- Python tooling (`python`, `python3`, `pip`, `pytest`, `ruff`)
- Docker commands
- Common file operations (`ls`, `mkdir`, `cp`, `mv`, `rm`, etc.)

### 3. Global Architecture Documentation

** - Canonical architecture doc:
- System overview with diagram
- Active repos with bounded contexts
- Future repos (placeholders for ike-crm, ike-backoffice)
- Deprecated repos list
- Infrastructure stack details
- Data flows
- Configuration reference
- Security tiers
- ADR conventions

### 4. ADR Aggregation

** - Cross-repo ADR index generator:
- Scans all active repos for `docs/decisions/*.md`
- Extracts metadata (status, date, title)
- Generates unified index with status summary and timeline

---

## Consequences

**Positive:**
- Single source of truth for auth (no more token conflicts)
- Every Claude Code session has system context from the start
- Faster development with pre-approved safe commands
- Architecture decisions visible across all repos
- New repos inherit sensible defaults

**Negative:**
- Token stored in plaintext in `~/.bashrc` (acceptable for single-user dev machine)
- Must regenerate token if exposed (happened 3x during setup - lesson learned)
- Global config could drift from project-specific needs

**Risks:**
- If `~/.bashrc` is compromised, GitHub access is compromised
- Global permissions could auto-approve something unintended (mitigated by conservative allowlist)

---

## Implementation Plan

### Phase 1: Authentication (Complete)
- [x] Remove conflicting keyring token
- [x] Switch ike-publisher from SSH to HTTPS
- [x] Add GITHUB_TOKEN to ~/.bashrc
- [x] Verify with `gh auth status`

### Phase 2: Claude Code Configuration (Complete)
- [x] Create ~/.claude/CLAUDE.md with global instructions
- [x] Create ~/.claude/settings.json with permission allowlist
- [x] Include architecture summary, auth rules, ADR conventions

### Phase 3: Architecture Documentation (Complete)
- [x] Create GLOBAL_ARCHITECTURE.md in ike-semantic-ops
- [x] Document all active/deprecated repos
- [x] Include infrastructure stack details
- [x] Add data flow diagrams

### Phase 4: ADR Aggregation (Complete)
- [x] Create aggregate_adrs.py script
- [x] Generate initial ADR_INDEX.md
- [x] Document aggregation process in GLOBAL_ARCHITECTURE.md

---

## Files Created/Modified

**Created:**
- `~/.claude/CLAUDE.md` - Global Claude Code instructions
- `~/.claude/settings.json` - Global permissions
- ` - Architecture doc
- ` - Aggregated ADR index
- ` - ADR aggregation script

**Modified:**
- `~/.bashrc` - Added GITHUB_TOKEN export
- ` - Changed remote from SSH to HTTPS

---

## References

- [GitHub Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [Claude Code Configuration](https://docs.anthropic.com/claude-code)
- [ADR Template](../decisions/TEMPLATE.md)

---

**End of Document**
