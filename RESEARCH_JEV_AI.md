# Research Report: TypeSafe AI & The Jev Model

**Date:** September 2026  
**Subject:** TypeSafe AI, Jev Model Architecture, System One Primitives, and Agent Integration Patterns  
**Primary Sources:** TypeSafe AI Documentation, OpenRouter API Specification, `typesafe-sdk` (v0.7.0), `blakestone-x/jev-mcp` (v0.2.1), `Brainwires/jevwire` (v0.4.0).

---

## 1. Executive Summary

**Jev** is a purpose-built, discriminative "System One" decision model launched in mid-September 2026 by **TypeSafe AI** (founded by Diogo Almeida, Erik Gafni, and Sasha Sheng, backed by DCVC).

Unlike traditional generative Large Language Models (LLMs) like GPT-4, Claude, or Gemini that generate unstructured text or autoregressively stream tokens, **Jev is fundamentally not a text generator**. It is a **deterministic, typed decision engine**.

You provide Jev with:
1. **State:** Arbitrary context (code snippets, git diffs, logs, error traces, JSON metadata, or prose).
2. **Questions:** A schema of typed questions evaluated simultaneously.

Jev returns **strictly typed, probabilistic decisions** (e.g., categorical choices with confidence distributions, rubric-based scores, or Bernoulli probabilities) in a single parallel forward pass with **~70–150 ms latency**.

---

## 2. Architecture & Design Principles: "System One"

The design of Jev is inspired by Daniel Kahneman’s behavioral economics framework:
- **System 1 (Jev):** Fast, instinctive, low-latency, parallel classification, routing, and bounded judgment.
- **System 2 (Claude Code / Codex / Gemini):** Deliberative, multi-step, sequential reasoning, planning, code writing, and tool execution.

### Key Characteristics:
1. **Zero Text Generation:** Jev has no tokenizer output stage for free-form prose. The output is bounded entirely by the caller-defined schema. There are no hallucinations of structure, syntax errors, or JSON decoding failures.
2. **Confidence on Every Decision:** Jev does not simply pick a category; it outputs calibrated probability distributions across all choices and an overall confidence score ($[0.0, 1.0]$).
3. **Hyper-Low Latency & Cost:**
   - **Cost:** ~$0.042 per million input tokens. **Output tokens are free ($0)** because output is fixed-size logits rather than autoregressively generated token streams.
   - **Speed:** ~70 ms to 150 ms per decision request.
   - **Context Window:** 32,000 tokens.

---

## 3. The Core Primitives

All decisions in Jev are expressed through three primitives:

| Primitive | Wire Type | Purpose | Returns |
| :--- | :--- | :--- | :--- |
| **Choice** | `choice` | Select exactly one label from a defined, closed set of options. | Selected label, full probability distribution across all labels, and `confidence` score ($0.0–1.0$). |
| **Score** | `score` | Place state along an ordered discrete rubric (at least 2 levels). | Calibrated expected score (continuous value across level indices), probability breakdown per level, and `confidence`. |
| **Noul** | `noul` | Bernoulli evaluation of a single proposition (Yes / No). | Scalar probability $P(\text{true}) \in [0.0, 1.0]$. |

### Question Schema Example
```json
{
  "state": {
    "command": "rm -rf /var/log/*",
    "cwd": "/home/app",
    "user_intent": "clear temporary caches"
  },
  "questions": {
    "is_destructive": {
      "type": "noul",
      "instructions": "Does this command permanently delete files outside the current project?"
    },
    "risk_level": {
      "type": "score",
      "instructions": "Rate the operational risk of running this command.",
      "criteria": [
        "harmless: read-only or temporary directory",
        "low: affects only project build artifacts",
        "high: modifies system files or non-reversible production state"
      ]
    },
    "category": {
      "type": "choice",
      "instructions": "Classify the primary action type of the command.",
      "criteria": {
        "cleanup": "Deleting cache or temporary files",
        "build": "Compiling or bundling assets",
        "system_admin": "System-wide administration tasks",
        "other": "Other unlisted operations"
      }
    }
  }
}
```

---

## 4. Primary Access Routes & Providers

There are two primary ways to access Jev:

### Route A: Direct TypeSafe AI
- **Endpoint:** `POST https://api.typesafe.ai/v1/systemone`
- **Models:** `jev-latest`, `jev-1.13.0`
- **Authentication:** Header `Authorization: Bearer <TYPESAFE_API_KEY>`
- **Status:** Currently rolling out via developer early access / waitlist at [typesafe.ai](https://typesafe.ai).
- **Official SDKs:**
  - Python: `typesafe-sdk` (`pip install typesafe-sdk`)
  - Node/TS: `@typesafe-ai/sdk` (`npm install @typesafe-ai/sdk`)
  - Vercel AI SDK: `@ai-sdk/typesafe-ai`

### Route B: OpenRouter Decisions API
- **Endpoint:** `POST https://openrouter.ai/api/alpha/decisions`
- **Models:** `typesafe/jev-1.13` (alias: `~typesafe/jev-latest`)
- **Authentication:** Header `Authorization: Bearer <OPENROUTER_API_KEY>`
- **Status:** Available immediately on OpenRouter without waiting for direct waitlist approval.
- **Important:** Jev **cannot** be called via OpenRouter's standard `/v1/chat/completions` endpoint because it does not accept messages or emit streaming text tokens. It requires the dedicated `/api/alpha/decisions` endpoint.

---

## 5. Ecosystem & MCP Implementations

Two prominent open-source projects provide agent harnesses and MCP servers for Jev:

### 1. `blakestone-x/jev-mcp` (Python / uvx)
- **Repo:** [blakestone-x/jev-mcp](https://github.com/blakestone-x/jev-mcp)
- **Stack:** Python 3.10+, Pydantic, FastMCP, `typesafe-sdk`.
- **Installation:** `uvx --from git+https://github.com/blakestone-x/jev-mcp@v0.2.1 jev-mcp`
- **Key Tools Exposed:**
  - `jev_ask`: Custom Choice, Score, and Noul question map against arbitrary state.
  - `jev_classify`: Selects one label from a closed set with distribution and confidence.
  - `jev_score`: Rates state along an ordered rubric.
  - `jev_check`: Independent yes/no checks (Nouls).
  - `jev_match`: Candidate matching with abstention (`exists` probability).
  - `jev_screen`: Fast filtering for instruction injection or untrusted text.
  - `jev_health`: Latency and model connectivity check.

### 2. `Brainwires/jevwire` (Node.js / npx)
- **Repo:** [Brainwires/jevwire](https://github.com/Brainwires/jevwire)
- **Stack:** TypeScript, Node.js 20+, zero-dependency bundled runtime.
- **Components:**
  1. **MCP Server:** `npx -y jevwire` (tools: `jev_rank`, `jev_verify`, `jev_evaluate`, `jev_gate_action`, `jev_next_step`, `jev_list_models`).
  2. **Claude Code Plugin:** Hooks directly into Claude Code lifecycle (`PreToolUse`, `PostToolUse`, `StopCheck`) without user prompts—hands notes and context directly to Claude.
  3. **Library:** `import { JevDecisionModel, runGateAction } from "jevwire"`.

---

## 6. Real-World Decision Benchmarks & Empirical Recipes

Primary evaluation data from production testing of Jev reveals several critical findings:

1. **Descriptions buy coverage, not precision:**
   - Plain label names: 64.5% agreement (735 tokens/req).
   - One-line `what` explanations: 81.0% agreement (1,689 tokens/req).
   - Detailed `what`, `not_for`, and `examples`: 84.5% agreement (4,745 tokens/req).
   - *Recommendation:* Start with clean one-line descriptions. Only add `not_for` and counter-examples to easily confused pairs.
2. **Calibration Curves:**
   - Confidence $\ge 0.8$: 95% agreement.
   - Confidence $0.7 - 0.8$: 71% agreement.
   - Confidence $< 0.6$: near random (50%).
   - *Action:* If confidence falls below $0.7$, agents should escalate to manual review or consult a full LLM.
3. **Batching is Nearly Free:**
   - Sending 20 related questions in a single Jev call only adds ~26 ms of latency and 6% extra tokens compared to 1 question, with virtually zero interference between questions.
4. **Order-Ensemble Abstention:**
   - Reversing label order in consecutive requests tests stability. If reversing label order changes the selected choice, the confidence is low (averaging 0.42), indicating genuine ambiguity.

---

## 7. Recommended Workflow for Coding Agents (Codex & Claude Code)

Instead of delegating code generation or architectural planning to Jev, use Jev as an **objective verification gate**:

```
[Agent explores & reasons]
           │
           ▼
[Draft Hypothesis / Root Cause] ────► Ask Jev: Classify hypothesis probability
           │
           ▼
[Edit Code & Run Tests]
           │
           ▼
[Git Diff & Test Output] ───────────► Ask Jev: Verify acceptance criteria satisfaction
           │
           ▼
[Report to User with Confidence]
```
