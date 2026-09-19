import unittest
import asyncio

import httpx

from src.gateway import JevProviderError, JevTimeoutError, JevGateway
from tests.test_gateway import QUESTIONS, valid_response


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class ResilienceTests(unittest.TestCase):
    def gateway(self, handler, fake_time, **kwargs):
        return JevGateway(openrouter_api_key="synthetic", http_transport=httpx.MockTransport(handler), clock=fake_time.clock, sleeper=fake_time.sleep, **kwargs)

    def test_recovers_from_retryable_status_with_exponential_backoff(self):
        responses = [httpx.Response(503), valid_response(None)]
        fake_time = FakeTime()
        gateway = self.gateway(lambda request: responses.pop(0), fake_time)
        self.assertEqual("billing", gateway.evaluate("state", QUESTIONS).answers["team"]["choice"])
        self.assertEqual([0.25], fake_time.sleeps)

    def test_respects_retry_after_and_attempt_limit(self):
        responses = [httpx.Response(429, headers={"retry-after": "0.5"}), httpx.Response(429), httpx.Response(429)]
        fake_time = FakeTime()
        gateway = self.gateway(lambda request: responses.pop(0), fake_time)
        with self.assertRaises(Exception) as caught:
            gateway.check("state", "Is it safe?")
        self.assertEqual("rate_limit", caught.exception.category)
        self.assertEqual([0.5, 0.5], fake_time.sleeps)

    def test_never_starts_retry_after_total_budget_is_exhausted(self):
        calls = []
        fake_time = FakeTime()
        gateway = self.gateway(lambda request: calls.append(request) or httpx.Response(503), fake_time, timeout_seconds=0.2)
        with self.assertRaises(JevTimeoutError):
            gateway.check("state", "Is it safe?")
        self.assertEqual(1, len(calls))
        self.assertEqual([], fake_time.sleeps)

    def test_does_not_retry_non_allowlisted_provider_status(self):
        calls = []
        fake_time = FakeTime()
        gateway = self.gateway(lambda request: calls.append(request) or httpx.Response(500), fake_time)
        with self.assertRaises(JevProviderError):
            gateway.check("state", "Is it safe?")
        self.assertEqual(1, len(calls))

    def test_oversized_retryable_error_preserves_status_and_retries(self):
        calls = []
        fake_time = FakeTime()
        responses = [httpx.Response(429, content=b"x" * 10_000), valid_response(None)]
        gateway = self.gateway(lambda request: calls.append(request) or responses.pop(0), fake_time, response_limit_bytes=1_024)
        self.assertEqual("billing", gateway.evaluate("state", QUESTIONS).answers["team"]["choice"])
        self.assertEqual(2, len(calls))

    def test_protocol_error_is_not_retried(self):
        calls = []
        fake_time = FakeTime()
        def fail(request):
            calls.append(request)
            raise httpx.LocalProtocolError("bad local protocol")
        gateway = self.gateway(fail, fake_time)
        with self.assertRaises(JevProviderError):
            gateway.evaluate("state", QUESTIONS)
        self.assertEqual(1, len(calls))


class AsyncResilienceTests(unittest.IsolatedAsyncioTestCase):
    async def test_total_deadline_cancels_slow_transport(self):
        cancelled = False

        async def slow_response(request):
            nonlocal cancelled
            try:
                import asyncio
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return valid_response(request)

        gateway = JevGateway(
            openrouter_api_key="synthetic",
            http_transport=httpx.MockTransport(slow_response),
            timeout_seconds=0.01,
        )
        with self.assertRaises(JevTimeoutError):
            await gateway.aevaluate("state", QUESTIONS)
        self.assertTrue(cancelled)

    async def test_deadline_cancels_slow_body_stream_and_closes_it(self):
        stream = BlockingStream()
        gateway = JevGateway(openrouter_api_key="synthetic", http_transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)), timeout_seconds=0.01)
        with self.assertRaises(JevTimeoutError):
            await gateway.aevaluate("state", QUESTIONS)
        self.assertTrue(stream.cancelled)
        self.assertTrue(stream.closed)

    async def test_caller_cancellation_closes_body_stream(self):
        stream = BlockingStream()
        gateway = JevGateway(openrouter_api_key="synthetic", http_transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)))
        task = asyncio.create_task(gateway.aevaluate("state", QUESTIONS))
        await stream.started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(stream.cancelled)
        self.assertTrue(stream.closed)

    async def test_overload_gate_releases_after_cancellation(self):
        stream = BlockingStream()
        gateway = JevGateway(openrouter_api_key="synthetic", max_in_flight=1, http_transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream)))
        task = asyncio.create_task(gateway.aevaluate("state", QUESTIONS))
        await stream.started.wait()
        with self.assertRaises(JevProviderError):
            await gateway.aevaluate("state", QUESTIONS)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        gateway._transport = httpx.MockTransport(valid_response)
        self.assertEqual("billing", (await gateway.aevaluate("state", QUESTIONS)).answers["team"]["choice"])

    async def test_authentication_and_malformed_success_are_not_retried(self):
        for response in (httpx.Response(401), httpx.Response(200, content=b"not json")):
            calls = []
            gateway = JevGateway(openrouter_api_key="synthetic", http_transport=httpx.MockTransport(lambda request, response=response: calls.append(request) or response))
            with self.assertRaises(Exception):
                await gateway.aevaluate("state", QUESTIONS)
            self.assertEqual(1, len(calls))


class BlockingStream(httpx.AsyncByteStream):
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False
        self.closed = False

    async def __aiter__(self):
        self.started.set()
        try:
            await asyncio.Event().wait()
            yield b""
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def aclose(self):
        self.closed = True
