# Harness Engineering — Claude Code Agent Contract

## Quality & Workflow Gates
- **TDD Workflow**: When adding new functionality, fixing bugs, or refactoring, activate and follow `.claude/skills/tdd-workflow/SKILL.md`. Always write a failing test first, verify the failure (RED), implement the minimal code to pass (GREEN), and refactor cleanly.
- **Verification Loop**: Before declaring any task complete or submitting code changes, activate and follow `.claude/skills/verification-loop/SKILL.md`. Verify build, type checks, lint, test suite with coverage, security scan, and diff review.

## Security & Operational Boundaries
- **Least Privilege**: Never read, print, or transmit secrets, tokens, or credentials.
- **Sandbox Isolation**: Confine all file reads and writes strictly to the project workspace. Never modify files outside the project root or in parent directories.
- **Test Integrity**: Never delete, weaken, or alter existing acceptance criteria, test assertions, or oracle tests to force a PASS. Tests must validate real system behavior.
- **Governance**: Do not execute destructive operations (`rm -rf`, dropping tables, git push/publish) without explicit operator authorization.
