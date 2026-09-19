# Jev gateway

Keep the gateway reusable: consuming projects own action policy and anti-rabbit-hole supervision.
Use offline tests with synthetic credentials by default. Live provider calls, credential access,
dependency installation and remote writes require explicit owner approval.

## Agent skills

### Issue tracker

Use local Markdown for specs and implementation tickets. Before creating or updating work,
read `docs/agents/issue-tracker.md`.

### Triage labels

Use the default role vocabulary in `docs/agents/triage-labels.md` when assigning ticket status.

### Domain docs

Use the single-context glossary and document rules in `docs/agents/domain.md` when planning
or changing gateway behaviour.

## Verification

Run `.venv/bin/python -m unittest discover -s tests -v` for the offline suite; use a module
such as `tests.test_resilience` for focused verification. Compile with
`.venv/bin/python -m compileall -q src tests examples`. No linter or type checker is installed.
Use an isolated test environment with synthetic credentials and temporary diagnostic logs.
Verify gateway behaviour through its public API and MCP behaviour through the standard stdio
transport; live examples are not tests. See `SETUP_GUIDE.md` for the supported contract.

The workspace sandbox can stall even `anyio.to_thread.run_sync(lambda: 1)`. If stdio tests
hang there, use an approved credential-free offline run outside that sandbox; retain the standard
MCP transport rather than adding a production workaround for the sandbox.
