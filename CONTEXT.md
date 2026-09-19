# Jev gateway

A shared gateway gives consuming agents structured Jev judgements. Each consuming project
decides how those judgements affect its actions.

## Language

**State**:
The caller-submitted context being judged, such as project code, task information or structured data.

**Question map**:
Named questions evaluated against the same state, with each name identifying its answer.

**Noul**:
A judgement of the probability that a proposition is true.
_Avoid_: Permission, authorisation

**Choice**:
A judgement selecting from caller-defined labels, with the provider's associated probabilities.

**Score**:
A judgement against a caller-defined ordered rubric.

**Judgement**:
A validated model answer to a question; it becomes an action decision only through a consuming project's policy.
_Avoid_: Approval, guarantee

**Consuming project**:
An application or agent workflow that calls the gateway and owns its action permissions, thresholds and fallback behaviour.

**Logging exclusion**:
A caller-designated field omitted from diagnostic records, independently of the state submitted for inference.

**Diagnostic record**:
A bounded, filtered record of a gateway request and its outcome, intended for troubleshooting rather than mandatory auditing.
