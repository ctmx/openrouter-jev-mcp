# Issue tracker: Local Markdown

Specs and tickets live in `.scratch/<feature-slug>/` and are versioned with the project.
The owner requested unattended setup through implementation on 2026-09-19. No remote is
configured, so local Markdown is the reversible setup default; no remote publication is authorised.

- Spec: `.scratch/<feature-slug>/spec.md`.
- Tickets: one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- Number tickets from 01 in dependency order. Record actual dependencies in `Blocked by`.
- Use `Status: ready-for-agent` for specified work, with unchecked acceptance criteria.
- Start only tickets whose blockers are complete and whose execution route is authorised.
- Record completion evidence and mark a ticket `done` only after its acceptance criteria pass.
- Append discussion under `Comments`; keep any execution blocker distinct from specification readiness.
- Publishing means writing these local files. Do not create remote issues or change a parent issue.

The current feature is `jev-gateway-hardening`. Its `progress.md` records execution state and
the outstanding delegation capability blocker; it is not independent verification evidence.
