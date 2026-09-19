# OpenRouter Decisions contract evidence

Checked on 2026-09-19. The gateway uses OpenRouter's documented TypeSafe model
alias and the TypeSafe System One wire schema as its validation contract. Applying
that schema to the alpha Decisions endpoint follows the existing integration and
the owner's live-tested handoff; live compatibility has not been reverified here.

- [OpenRouter's TypeSafe model page](https://openrouter.ai/typesafe) identifies
  the `~typesafe/jev-latest` alias as the current Jev alias and says TypeSafe
  models are available through OpenRouter.
- [TypeSafe's System One overview](https://docs.typesafe.ai/concepts/system-one)
  says Jev accepts strings, JSON objects and arrays of text, and returns typed
  answers and probabilities.
- [TypeSafe's HTTP API reference](https://docs.typesafe.ai/api) specifies the
  model, state and questions request and model, answers and usage response.
  Its primitive sections define noul, choice and score; Choice and Score
  answers include distributions and confidence, and Score includes a numbered
  legend. Probability distributions sum to one. The response examples provide
  the synthetic fixtures used by tests/test_gateway.py.

The OpenRouter Decisions route remains alpha and does not have a separately
published schema page in the current OpenRouter documentation. This slice keeps
the established endpoint (POST https://openrouter.ai/api/alpha/decisions) and
does not add fields beyond TypeSafe's published contract. A future live smoke
test, if explicitly authorised, should recheck route availability and schema.

Validation choices derived from those sources:

- state is a JSON-compatible string, object or list; non-finite values cannot
  be encoded as JSON;
- every request question and response answer has the same named id and type;
- Noul is a finite number in [0, 1];
- Choice selects a supplied label and returns exactly its labels as a finite
  [0, 1] distribution summing to one, plus confidence in [0, 1];
- Score is finite in the supplied level range and returns matching numbered
  legend and distribution, plus confidence in [0, 1].
