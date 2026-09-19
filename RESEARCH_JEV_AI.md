# Jev research notes

Checked against primary sources on 19 September 2026. Provider details can change;
these notes describe the model and distinguish provider claims from this project's
verification. See [README.md](README.md) for installation and
[SETUP_GUIDE.md](SETUP_GUIDE.md) for the gateway contract.

## Model and primitives

[TypeSafe's introduction](https://docs.typesafe.ai/introduction) describes Jev as a
System One model that evaluates typed questions against caller-supplied state and
returns structured decisions rather than free-form prose.

| Primitive | Purpose | Answer fields |
| --- | --- | --- |
| Choice | Select a caller-defined label | `choice`, `probabilities`, `confidence` |
| Score | Evaluate an ordered rubric | `score`, `probabilities`, `confidence` |
| Noul | Evaluate a proposition | `noul`, a value from 0 to 1 |

TypeSafe documents evaluating multiple questions independently against the same
state in one request. Typed outputs constrain the answer format; they do not prove
that a judgement is correct. Model scores are advisory inputs to application policy,
not authorisation or a substitute for tests.

## OpenRouter listing

[OpenRouter's Jev 1.13 page](https://openrouter.ai/typesafe/jev-1.13) listed:

- $0.042 per million input tokens and $0 per million output tokens.
- A 32,000-token context window.
- Approximately 260 ms median provider latency at the time of review.

These are provider figures, not measurements of this gateway. Network overhead,
request size, retries and provider load affect end-to-end latency and cost.
[The `~typesafe/jev-latest` alias](https://openrouter.ai/~typesafe/jev-latest) follows
the latest Jev model, so it does not pin model behaviour to one release.

## Gateway integration and evidence limits

This project uses `POST https://openrouter.ai/api/alpha/decisions` with an OpenRouter
API key. The route is alpha. The integration follows the existing project endpoint
and [TypeSafe's published HTTP schema](https://docs.typesafe.ai/api); a separate
OpenRouter Decisions schema page was not located during this review. Live endpoint
compatibility has not been reverified as part of the publication cleanup.

Offline tests use synthetic credentials and mock provider responses. They verify
request validation, response validation, retries, diagnostic filtering and MCP
transport behaviour. They do not establish live availability, model accuracy,
calibration on coding tasks or production latency.

The project has no reproducible benchmark supporting universal confidence
thresholds or the earlier task-agreement percentages. Choose thresholds using
representative evaluations of the consuming application's own tasks, and retain
its independent action-permission and error-handling rules.

## Native TypeSafe access

[TypeSafe's website](https://typesafe.ai/) displayed a developer waitlist when
reviewed. Native credentials and SDK routing are outside this gateway's supported
contract. `examples/demo_typesafe_sdk.py` remains a historical experiment; its
optional dependency and API compatibility are not covered by the installation or
offline tests.
