# Issue tracker: Local Markdown

Local specs and tickets live in `.scratch/<feature-slug>/`, which is ignored by Git.
Create them when work needs a durable specification or spans multiple sessions.
For small changes, use the owner's request and report the result directly.

- Spec: `.scratch/<feature-slug>/spec.md`.
- Tickets: one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- Number tickets from 01 in dependency order. Record actual dependencies in `Blocked by`.
- Use `Status: ready-for-agent` for specified work, with unchecked acceptance criteria.
- Start only tickets whose blockers are complete and whose execution route is authorised.
- Record completion evidence and mark a ticket `done` only after its acceptance criteria pass.
- Append discussion under `Comments`; keep any execution blocker distinct from specification readiness.
- Creating or updating local tickets does not authorise remote issues, pushes or publication.
  Use the owner's current instructions to determine which remote actions are authorised.
