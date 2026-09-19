import unittest

from src import server


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_registers_five_tools_with_any_state_schema(self):
        tools = await server.app.list_tools()
        by_name = {tool.name: tool for tool in tools}
        self.assertEqual({"jev_check", "jev_classify", "jev_score", "jev_evaluate", "jev_health"}, set(by_name))
        self.assertNotIn("type", by_name["jev_check"].input_schema["properties"]["state"])

    async def test_health_reports_configuration_as_a_structured_result(self):
        original = server.gateway
        try:
            from src.gateway import JevGateway
            server.gateway = JevGateway(openrouter_api_key=None, typesafe_api_key=None)
            self.assertEqual("configuration", (await server.jev_health())["error"]["category"])
        finally:
            server.gateway = original
