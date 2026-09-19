import json
import math
import os
import gzip
import unittest
from unittest.mock import patch

import httpx

from src.gateway import (
    JevAuthenticationError,
    JevConfigurationError,
    JevGateway,
    JevInputError,
    JevProviderError,
    JevProviderResponseError,
    JevRateLimitError,
    JevTimeoutError,
)


QUESTIONS = {
    "urgent": {"type": "noul", "instructions": "Is this urgent?"},
    "team": {"type": "choice", "instructions": "Which team?", "criteria": {"billing": "Payments", "technical": "Bugs"}},
    "severity": {"type": "score", "instructions": "How severe?", "criteria": ["low", "high"]},
}


def valid_response(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "model": "typesafe/jev-1.13",
        "answers": {
            "urgent": {"type": "noul", "noul": 0.9},
            "team": {"type": "choice", "choice": "billing", "probabilities": {"billing": 0.8, "technical": 0.2}, "confidence": 0.7},
            "severity": {"type": "score", "score": 0.8, "legend": {"0": "low", "1": "high"}, "probabilities": {"0": 0.2, "1": 0.8}, "confidence": 0.6},
        },
        "usage": {"input_tokens": 3, "output_tokens": 1},
    })


class GatewayTests(unittest.TestCase):
    def gateway(self, handler=valid_response, **kwargs):
        return JevGateway(openrouter_api_key="synthetic-key", http_transport=httpx.MockTransport(handler), **kwargs)

    def test_evaluate_returns_valid_mixed_judgements(self):
        result = self.gateway().evaluate("The payment failed", QUESTIONS)
        self.assertEqual("typesafe/jev-1.13", result.model)
        self.assertEqual("billing", result.answers["team"]["choice"])
        self.assertEqual(0.8, result.answers["severity"]["score"])

    def test_rejects_non_json_state_before_outbound_request(self):
        calls = []
        gateway = self.gateway(lambda request: calls.append(request) or valid_response(request))
        invalid = [{"bad": math.nan}, {1: "key"}, {"tuple": ("not", "json")}, {"set": {"not-json"}}]
        for state in invalid:
            with self.assertRaises(JevInputError):
                gateway.evaluate(state, {"question": QUESTIONS["urgent"]})
        self.assertEqual([], calls)

    def test_rejects_cyclic_and_overdeep_json_without_raw_recursion_errors(self):
        cyclic = []
        cyclic.append(cyclic)
        state = cyclic
        with self.assertRaises(JevInputError):
            self.gateway().evaluate(state, {"question": QUESTIONS["urgent"]})
        nested = "leaf"
        for _ in range(65):
            nested = [nested]
        with self.assertRaises(JevInputError):
            self.gateway().evaluate(nested, {"question": QUESTIONS["urgent"]})

    def test_rejects_nonfinite_values_anywhere_in_provider_response(self):
        body = json.dumps({"model": "m", "answers": valid_response(None).json()["answers"], "usage": {"cost": math.nan}}, allow_nan=True).encode()
        with self.assertRaises(JevProviderResponseError):
            self.gateway(lambda request: httpx.Response(200, content=body)).evaluate("state", QUESTIONS)

    def test_rejects_request_and_question_limits_before_outbound_request(self):
        calls = []
        handler = lambda request: calls.append(request) or valid_response(request)
        with self.assertRaises(JevInputError):
            self.gateway(handler, request_limit_bytes=30).check("too long for this request", "Is it safe?")
        with self.assertRaises(JevInputError):
            self.gateway(handler, max_questions=1).evaluate("state", {"a": QUESTIONS["urgent"], "b": QUESTIONS["urgent"]})
        self.assertEqual([], calls)

    def test_rejects_huge_state_before_json_serialisation_or_outbound_request(self):
        calls = []
        gateway = self.gateway(lambda request: calls.append(request) or valid_response(request))
        with self.assertRaises(JevInputError):
            gateway.check("x" * 1_000_000, "Is it safe?")
        self.assertEqual([], calls)

    def test_rejects_huge_question_before_question_serialisation(self):
        question = {"type": "choice", "instructions": "x" * 1_000_000, "criteria": {"a": "also oversized " * 100_000}}
        with patch("src.gateway._json_bytes", side_effect=AssertionError("encoder must not run")):
            with self.assertRaises(JevInputError):
                self.gateway().evaluate("state", {"huge": question})

    def test_missing_answers_and_invalid_primitive_values_are_provider_errors(self):
        invalid_answers = [
            {},
            {"urgent": {"type": "noul", "noul": math.nan}, "team": valid_response(None).json()["answers"]["team"], "severity": valid_response(None).json()["answers"]["severity"]},
            {"urgent": {"type": "noul", "noul": 2}, "team": valid_response(None).json()["answers"]["team"], "severity": valid_response(None).json()["answers"]["severity"]},
            {"urgent": valid_response(None).json()["answers"]["urgent"], "team": {"type": "choice", "choice": "unknown", "probabilities": {"billing": 0.8, "technical": 0.2}, "confidence": 0.7}, "severity": valid_response(None).json()["answers"]["severity"]},
            {"urgent": valid_response(None).json()["answers"]["urgent"], "team": {"type": "choice", "choice": "billing", "probabilities": {"billing": 1.2, "technical": -0.2}, "confidence": math.inf}, "severity": valid_response(None).json()["answers"]["severity"]},
            {"urgent": valid_response(None).json()["answers"]["urgent"], "team": valid_response(None).json()["answers"]["team"], "severity": {"type": "score", "score": 2, "legend": {"0": "low", "1": "wrong"}, "probabilities": {"0": 0.2, "1": 0.8}, "confidence": math.inf}},
        ]
        for answers in invalid_answers:
            body = json.dumps({"model": "m", "answers": answers, "usage": {}}, allow_nan=True).encode()
            gateway = self.gateway(lambda request, body=body: httpx.Response(200, content=body))
            with self.assertRaises(JevProviderResponseError):
                gateway.evaluate("state", QUESTIONS)

    def test_response_limit_and_redirect_are_provider_errors(self):
        with self.assertRaises(JevProviderResponseError):
            self.gateway(lambda request: httpx.Response(200, content=b"{" + b"x" * 100), response_limit_bytes=32).check("state", "Is it safe?")
        with self.assertRaises(JevProviderError):
            self.gateway(lambda request: httpx.Response(302, headers={"location": "https://example.invalid"})).check("state", "Is it safe?")

    def test_rejects_compressed_success_without_decoding_it(self):
        with self.assertRaises(JevProviderResponseError):
            self.gateway(lambda request: httpx.Response(200, headers={"content-encoding": "gzip"}, content=gzip.compress(b"small compressed body"))).check("state", "Is it safe?")

    def test_http_error_categories_are_sanitised(self):
        cases = [(401, JevAuthenticationError), (429, JevRateLimitError), (504, JevTimeoutError), (500, JevProviderError)]
        for status, error_type in cases:
            with self.assertRaises(error_type) as caught:
                self.gateway(lambda request, status=status: httpx.Response(status, content=b"Bearer synthetic-key body")).check("state", "Is it safe?")
            self.assertNotIn("synthetic-key", str(caught.exception))

    def test_transport_errors_are_sanitised_without_context(self):
        def fail(_: httpx.Request):
            raise httpx.ConnectError("Bearer synthetic-key leaked")
        with self.assertRaises(JevProviderError) as caught:
            self.gateway(fail).check("state", "Is it safe?")
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn("synthetic-key", str(caught.exception))

    def test_configuration_is_explicit_and_does_not_depend_on_ambient_environment(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(JevGateway().health()["ready"])
            with self.assertRaises(JevConfigurationError):
                JevGateway(typesafe_api_key="native-only").check("state", "Is it safe?")
            gateway = JevGateway(openrouter_api_key="synthetic", typesafe_api_key="also-native")
            self.assertEqual("openrouter", gateway.provider)
            self.assertTrue(gateway.health()["ready"])
            for invalid in ("", 1):
                with self.assertRaises(JevConfigurationError):
                    JevGateway(openrouter_api_key=invalid)
            with self.assertRaises(JevConfigurationError):
                JevGateway(model="")

    def test_sync_api_rejects_running_event_loop(self):
        async def call_sync_api():
            with self.assertRaisesRegex(RuntimeError, "asynchronous methods"):
                self.gateway().check("state", "Is it safe?")
        import asyncio
        asyncio.run(call_sync_api())
