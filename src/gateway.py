"""Validated synchronous client for OpenRouter's Jev Decisions endpoint."""

from __future__ import annotations

import asyncio
import json
import math
import os
import threading
import time
import uuid
from email.utils import parsedate_to_datetime
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Union

import httpx
from src.diagnostics import DiagnosticLogger, validate_exclusions

DEFAULT_OPENROUTER_MODEL = "~typesafe/jev-latest"
OPENROUTER_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_REQUEST_LIMIT_BYTES = 262_144
DEFAULT_RESPONSE_LIMIT_BYTES = 262_144
DEFAULT_MAX_QUESTIONS = 64
DEFAULT_MAX_IN_FLIGHT = 8
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.25
RETRYABLE_STATUS_CODES = frozenset({408, 429, 502, 503, 504})

JsonState = Union[str, dict[str, Any], list[Any]]


class JevGatewayError(Exception):
    category = "provider_failure"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"category": self.category, "message": self.message}}


class JevConfigurationError(JevGatewayError):
    category = "configuration"


class JevInputError(JevGatewayError):
    category = "input_validation"


class JevTimeoutError(JevGatewayError):
    category = "timeout"


class JevAuthenticationError(JevGatewayError):
    category = "authentication"


class JevRateLimitError(JevGatewayError):
    category = "rate_limit"


class JevProviderError(JevGatewayError):
    category = "provider_failure"


class JevProviderResponseError(JevGatewayError):
    category = "provider_response"


@dataclass(frozen=True)
class DecisionResult:
    model: str
    answers: dict[str, Any]
    usage: dict[str, Any]
    raw_response: dict[str, Any]


class JevGateway:
    """OpenRouter-only Jev client; consuming projects own action policy."""

    def __init__(
        self,
        openrouter_api_key: Optional[str] = None,
        typesafe_api_key: Optional[str] = None,
        model: Optional[str] = None,
        *,
        http_transport: Optional[httpx.AsyncBaseTransport] = None,
        request_limit_bytes: int = DEFAULT_REQUEST_LIMIT_BYTES,
        response_limit_bytes: int = DEFAULT_RESPONSE_LIMIT_BYTES,
        max_questions: int = DEFAULT_MAX_QUESTIONS,
        max_in_flight: int = DEFAULT_MAX_IN_FLIGHT,
        timeout_seconds: float = 20.0,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        clock: Any = time.monotonic,
        sleeper: Any = asyncio.sleep,
        logger: Optional[DiagnosticLogger] = None,
    ) -> None:
        self.openrouter_api_key = _configuration_string(
            openrouter_api_key if openrouter_api_key is not None else os.environ.get("OPENROUTER_API_KEY"),
            "OPENROUTER_API_KEY",
        )
        self.typesafe_api_key = typesafe_api_key if typesafe_api_key is not None else os.environ.get("TYPESAFE_API_KEY")
        if self.typesafe_api_key is not None and not isinstance(self.typesafe_api_key, str):
            raise JevConfigurationError("TYPESAFE_API_KEY must be a string when supplied.")
        self.model = _model(model)
        self.provider = "openrouter"
        self.request_limit_bytes = _positive_int(request_limit_bytes, "request_limit_bytes")
        self.response_limit_bytes = _positive_int(response_limit_bytes, "response_limit_bytes")
        self.max_questions = _positive_int(max_questions, "max_questions")
        self.timeout_seconds = _positive_number(timeout_seconds, "timeout_seconds")
        self.max_attempts = _positive_int(max_attempts, "max_attempts")
        self.retry_backoff_seconds = _positive_number(retry_backoff_seconds, "retry_backoff_seconds")
        self._clock = clock
        self._sleeper = sleeper
        self._slots = threading.BoundedSemaphore(_positive_int(max_in_flight, "max_in_flight"))
        self._transport = http_transport
        self.logger = logger or DiagnosticLogger()
        self.logger.add_secret(self.openrouter_api_key)

    def close(self) -> None:
        self.logger.close()

    def __enter__(self) -> "JevGateway":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def health(self, verify: bool = False) -> dict[str, Any]:
        health = {"ready": bool(self.openrouter_api_key), "connectivity": "unverified", "provider": self.provider, "model": self.model}
        if not self.openrouter_api_key:
            health["error"] = self._configuration_error().to_dict()["error"]
        elif verify:
            self.check("health probe", "Is this a health probe?")
            health["connectivity"] = "verified"
        return health

    def evaluate(self, state: JsonState, questions: Mapping[str, Any], *, logging_exclusions: list[str] | None = None) -> DecisionResult:
        return _run_sync(self.aevaluate(state, questions, logging_exclusions=logging_exclusions))

    async def aevaluate(self, state: JsonState, questions: Mapping[str, Any], *, logging_exclusions: list[str] | None = None) -> DecisionResult:
        try:
            validate_exclusions(logging_exclusions)
        except ValueError as exc:
            raise JevInputError(str(exc)) from None
        started = self._clock()
        request_id = str(uuid.uuid4())
        try:
            result = await self._aevaluate(state, questions)
        except JevGatewayError as error:
            self.logger.record("judgement", metadata={"request_id": request_id, "outcome": error.category, "duration_ms": int((self._clock() - started) * 1000)}, exclusions=logging_exclusions)
            raise
        self.logger.record("judgement", state=state, answers=result.answers,
                           metadata={"request_id": request_id, "outcome": "success", "model": result.model, "duration_ms": int((self._clock() - started) * 1000)}, exclusions=logging_exclusions)
        return result

    async def _aevaluate(self, state: JsonState, questions: Mapping[str, Any]) -> DecisionResult:
        self._require_configuration()
        _preflight_json_bytes({"model": self.model, "state": state, "questions": questions}, self.request_limit_bytes)
        validated_questions = _questions(questions, self.max_questions)
        payload = {"model": self.model, "state": _state(state), "questions": validated_questions}
        body = _json_bytes(payload, JevInputError, "request is not JSON-compatible")
        if len(body) > self.request_limit_bytes:
            raise JevInputError(f"request exceeds {self.request_limit_bytes} byte limit.")
        if not self._slots.acquire(blocking=False):
            raise JevProviderError("gateway has reached its in-flight request limit.")
        try:
            return _response(await self._post(body), validated_questions)
        finally:
            self._slots.release()

    def check(self, state: JsonState, proposition: str, *, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
        if not isinstance(proposition, str) or not proposition.strip():
            raise JevInputError("proposition must be a non-empty string.")
        result = self.evaluate(state, {"check": {"type": "noul", "instructions": proposition}}, logging_exclusions=logging_exclusions)
        return result.answers["check"]

    async def acheck(self, state: JsonState, proposition: str, *, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
        if not isinstance(proposition, str) or not proposition.strip():
            raise JevInputError("proposition must be a non-empty string.")
        result = await self.aevaluate(state, {"check": {"type": "noul", "instructions": proposition}}, logging_exclusions=logging_exclusions)
        return result.answers["check"]

    def choice(self, state: JsonState, instructions: Any, options: Mapping[str, Optional[str]], *, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
        result = self.evaluate(state, {"selection": {"type": "choice", "instructions": instructions, "criteria": options}}, logging_exclusions=logging_exclusions)
        return result.answers["selection"]

    async def achoice(self, state: JsonState, instructions: Any, options: Mapping[str, Optional[str]], *, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
        result = await self.aevaluate(state, {"selection": {"type": "choice", "instructions": instructions, "criteria": options}}, logging_exclusions=logging_exclusions)
        return result.answers["selection"]

    def score(self, state: JsonState, instructions: Any, rubric: list[str], *, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
        result = self.evaluate(state, {"score": {"type": "score", "instructions": instructions, "criteria": rubric}}, logging_exclusions=logging_exclusions)
        return result.answers["score"]

    async def ascore(self, state: JsonState, instructions: Any, rubric: list[str], *, logging_exclusions: list[str] | None = None) -> dict[str, Any]:
        result = await self.aevaluate(state, {"score": {"type": "score", "instructions": instructions, "criteria": rubric}}, logging_exclusions=logging_exclusions)
        return result.answers["score"]

    def _configuration_error(self) -> JevConfigurationError:
        if self.typesafe_api_key:
            return JevConfigurationError("Native TypeSafe configuration is unsupported; configure OPENROUTER_API_KEY.")
        return JevConfigurationError("OPENROUTER_API_KEY is not configured.")

    def _require_configuration(self) -> None:
        if not self.openrouter_api_key:
            raise self._configuration_error()

    async def _post(self, body: bytes) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.openrouter_api_key}", "Content-Type": "application/json", "Accept-Encoding": "identity"}
        deadline = self._clock() + self.timeout_seconds
        try:
            async with httpx.AsyncClient(transport=self._transport) as client:
                async with asyncio.timeout(self.timeout_seconds):
                    for attempt in range(self.max_attempts):
                        if self._clock() >= deadline:
                            raise JevTimeoutError("OpenRouter request deadline exhausted.")
                        try:
                            async with client.stream("POST", OPENROUTER_DECISIONS_URL, headers=headers, content=body) as response:
                                if not response.is_success:
                                    retry_after = _retry_after(response)
                                    error = _http_error(response)
                                    may_retry = response.status_code in RETRYABLE_STATUS_CODES
                                elif response.headers.get("content-encoding", "identity").lower() != "identity":
                                    error, retry_after, may_retry = JevProviderResponseError("OpenRouter returned unsupported content encoding."), None, False
                                else:
                                    return _parse_response(await _read_limited_async(response, self.response_limit_bytes))
                        except httpx.TimeoutException:
                            error, retry_after, may_retry = JevTimeoutError("OpenRouter request timed out."), None, True
                        except httpx.ConnectError:
                            error, retry_after, may_retry = JevProviderError("OpenRouter request failed."), None, True
                        except httpx.HTTPError:
                            error, retry_after, may_retry = JevProviderError("OpenRouter request failed."), None, False
                        if not may_retry or attempt + 1 >= self.max_attempts:
                            raise error from None
                        delay = retry_after if retry_after is not None else self.retry_backoff_seconds * (2 ** attempt)
                        if delay >= deadline - self._clock():
                            raise JevTimeoutError("OpenRouter request deadline exhausted.")
                        await self._sleeper(delay)
        except TimeoutError:
            raise JevTimeoutError("OpenRouter request deadline exhausted.") from None
        raise JevProviderError("OpenRouter request failed.")


def _parse_response(content: bytes) -> dict[str, Any]:
    try:
        response = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise JevProviderResponseError("OpenRouter returned invalid JSON.") from None
    if not isinstance(response, dict):
        raise JevProviderResponseError("OpenRouter response must be an object.")
    if not _is_json(response):
        raise JevProviderResponseError("OpenRouter response contains invalid JSON values.")
    return response


def _configuration_string(value: Any, name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise JevConfigurationError(f"{name} must be a non-empty string when supplied.")
    return value


def _model(model: Any) -> str:
    if model is None:
        return DEFAULT_OPENROUTER_MODEL
    if not isinstance(model, str) or not model.strip():
        raise JevConfigurationError("model must be a non-empty string when supplied.")
    return model


def _positive_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return float(value)


def _json_bytes(value: Any, error: type[JevGatewayError], message: str) -> bytes:
    if not _is_json(value):
        raise error(message)
    try:
        return json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError):
        raise error(message) from None


def _preflight_json_bytes(value: Any, limit: int) -> None:
    """Conservatively bound JSON before materialising the encoded request."""
    total = 2
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str):
            total += 2 + _bounded_utf8_length(item, limit - total) * 12
        elif isinstance(item, dict):
            total += 2 + len(item)
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            total += 2 + len(item)
            pending.extend(item)
        else:
            total += 32
        if total > limit:
            raise JevInputError(f"request exceeds {limit} byte limit.")


def _bounded_utf8_length(value: str, remaining: int) -> int:
    """Count UTF-8 bytes without allocating an encoded copy of an untrusted string."""
    total = 0
    for character in value:
        ordinal = ord(character)
        total += 1 if ordinal < 0x80 else 2 if ordinal < 0x800 else 3 if ordinal < 0x10000 else 4
        if total > remaining:
            raise JevInputError("request exceeds configured byte limit.")
    return total


def _is_json(value: Any) -> bool:
    return _is_json_value(value, depth=0, active=set())


def _is_json_value(value: Any, depth: int, active: set[int]) -> bool:
    if depth > 64:
        return False
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)):
        return not isinstance(value, bool) and math.isfinite(value) and (not isinstance(value, int) or abs(value) <= 10**308)
    if isinstance(value, list):
        identity = id(value)
        if identity in active:
            return False
        active.add(identity)
        try:
            return all(_is_json_value(item, depth + 1, active) for item in value)
        finally:
            active.remove(identity)
    if isinstance(value, dict):
        identity = id(value)
        if identity in active:
            return False
        active.add(identity)
        try:
            return all(isinstance(key, str) and _is_json_value(item, depth + 1, active) for key, item in value.items())
        finally:
            active.remove(identity)
    return False


def _state(value: Any) -> JsonState:
    if not isinstance(value, (str, dict, list)) or not _is_json(value):
        raise JevInputError("state must be a JSON-compatible string, object, or list.")
    return value


def _instructions(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, (dict, list)) and bool(value) and _is_json(value)


def _questions(value: Any, maximum: int) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or not value:
        raise JevInputError("questions must be a non-empty map.")
    if len(value) > maximum:
        raise JevInputError(f"questions exceeds {maximum} question limit.")
    result: dict[str, dict[str, Any]] = {}
    for name, item in value.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(item, Mapping):
            raise JevInputError("each question needs a non-empty string id and object definition.")
        kind, instructions, criteria = item.get("type"), item.get("instructions"), item.get("criteria")
        if kind not in ("noul", "choice", "score") or not _instructions(instructions):
            raise JevInputError("question has invalid type or instructions.")
        question: dict[str, Any] = {"type": kind, "instructions": instructions}
        if kind == "noul" and criteria is not None:
            if not isinstance(criteria, Mapping) or set(criteria) - {"true", "false"} or not all(isinstance(text, str) and text.strip() for text in criteria.values()):
                raise JevInputError("question has invalid noul criteria.")
            question["criteria"] = dict(criteria)
        elif kind == "choice":
            if not isinstance(criteria, Mapping) or not criteria or not all(isinstance(label, str) and label.strip() and (text is None or isinstance(text, str)) for label, text in criteria.items()):
                raise JevInputError("question has invalid choice criteria.")
            question["criteria"] = dict(criteria)
        elif kind == "score":
            if not isinstance(criteria, list) or len(criteria) < 2 or not all(isinstance(level, str) and level.strip() for level in criteria):
                raise JevInputError("question needs at least two non-empty score levels.")
            question["criteria"] = list(criteria)
        _json_bytes(question, JevInputError, "question is not JSON-compatible")
        result[name] = question
    return result


def _probability(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and 0 <= value <= 1


def _probabilities(value: Any, expected: set[str]) -> None:
    if not isinstance(value, Mapping) or set(value) != expected or not all(_probability(item) for item in value.values()):
        raise JevProviderResponseError("provider probabilities are invalid.")
    if not math.isclose(sum(value.values()), 1.0, abs_tol=1e-6):
        raise JevProviderResponseError("provider probabilities are invalid.")


def _response(data: dict[str, Any], questions: Mapping[str, Mapping[str, Any]]) -> DecisionResult:
    model, answers, usage = data.get("model"), data.get("answers"), data.get("usage")
    if not isinstance(model, str) or not model or not isinstance(answers, Mapping) or not isinstance(usage, Mapping):
        raise JevProviderResponseError("OpenRouter response is missing required model, answers, or usage.")
    if set(answers) != set(questions):
        raise JevProviderResponseError("OpenRouter response answers do not match requested questions.")
    checked: dict[str, Any] = {}
    for name, question in questions.items():
        answer = answers[name]
        kind = question["type"]
        if not isinstance(answer, Mapping) or answer.get("type") != kind:
            raise JevProviderResponseError("provider answer has the wrong type.")
        if kind == "noul":
            if not _probability(answer.get("noul")):
                raise JevProviderResponseError("provider noul value is invalid.")
        elif kind == "choice":
            labels = set(question["criteria"])
            if not isinstance(answer.get("choice"), str) or answer["choice"] not in labels:
                raise JevProviderResponseError("provider choice is invalid.")
            _probabilities(answer.get("probabilities"), labels)
            if not _probability(answer.get("confidence")):
                raise JevProviderResponseError("provider confidence is invalid.")
        else:
            levels, score = question["criteria"], answer.get("score")
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= len(levels) - 1:
                raise JevProviderResponseError("provider score is invalid.")
            expected = {str(index) for index in range(len(levels))}
            if answer.get("legend") != {str(index): level for index, level in enumerate(levels)}:
                raise JevProviderResponseError("provider score legend is invalid.")
            _probabilities(answer.get("probabilities"), expected)
            if not _probability(answer.get("confidence")):
                raise JevProviderResponseError("provider confidence is invalid.")
        checked[name] = dict(answer)
    return DecisionResult(model, checked, dict(usage), data)


async def _read_limited_async(response: httpx.Response, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes(chunk_size=min(65_536, limit)):
        size += len(chunk)
        if size > limit:
            raise JevProviderResponseError(f"OpenRouter response exceeds {limit} byte limit.")
        chunks.append(chunk)
    return b"".join(chunks)


def _run_sync(awaitable: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    awaitable.close()
    raise RuntimeError("Use JevGateway's asynchronous methods from a running event loop.")


def _http_error(response: httpx.Response) -> JevGatewayError:
    if response.status_code in (401, 403):
        return JevAuthenticationError("OpenRouter rejected the configured credentials.")
    if response.status_code == 429:
        return JevRateLimitError("OpenRouter rate limit exceeded.")
    if response.status_code in (408, 504):
        return JevTimeoutError("OpenRouter request timed out.")
    return JevProviderError(f"OpenRouter returned HTTP {response.status_code}.")


def _retry_after(response: httpx.Response) -> Optional[float]:
    if response.status_code not in RETRYABLE_STATUS_CODES:
        return None
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = (parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None
