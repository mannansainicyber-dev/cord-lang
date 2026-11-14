import asyncio
import pytest
from cord.lexer import Lexer
from cord.parser import Parser
from cord.interpreter import Interpreter
from cord.discord_adapter import MockDiscordAdapter
from cord.runtime import CordHttpResponse, cord_fetch, CordHttpModule, get_standard_environment


def test_cord_http_response_properties():
    json_text = '{"name": "CordBot", "stars": 42, "features": ["fast", "clean"]}'
    res = CordHttpResponse(status=200, text=json_text, headers={"content-type": "application/json"}, url="https://example.com/api")

    assert res.status == 200
    assert res.ok is True
    assert res.text == json_text
    assert res.data["name"] == "CordBot"
    assert res.data["stars"] == 42
    # Test dictionary / attribute access
    assert res["stars"] == 42
    assert res.name == "CordBot"
    assert res.features[0] == "fast"


def test_cord_http_response_error_status():
    res = CordHttpResponse(status=404, text="Not Found", headers={}, url="https://example.com/missing")
    assert res.status == 404
    assert res.ok is False
    assert res.data is None
    assert res.text == "Not Found"


def test_cord_fetch_mocked(monkeypatch):
    def fake_sync_http(url, method="GET", headers=None, body=None, timeout=30.0):
        if "weather" in url:
            return CordHttpResponse(200, '{"temperature": 22, "city": "Tokyo"}', {}, url)
        elif "post" in url:
            return CordHttpResponse(201, '{"status": "created"}', {}, url)
        return CordHttpResponse(404, '{"error": "not found"}', {}, url)

    import cord.runtime
    monkeypatch.setattr(cord.runtime, "_sync_http_request", fake_sync_http)

    async def _run():
        code = (
            'command weather:\n'
            '    res = fetch("https://api.test/weather")\n'
            '    reply "Temp in {res.city} is {res.temperature}C"\n'
            '\n'
            'command submit:\n'
            '    res = http.post("https://api.test/post", json={"user": "mannan"})\n'
            '    if res.ok:\n'
            '        reply "Successfully posted: {res.status}"\n'
        )
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)
        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()

        await interpreter.execute_program(program, ctx=adapter)

        # 1. Dispatch !weather
        await adapter.dispatch_prefix_command("!weather")
        assert len(adapter.sent_messages) == 1
        assert adapter.sent_messages[0]["content"] == "Temp in Tokyo is 22C"

        # 2. Dispatch !submit
        await adapter.dispatch_prefix_command("!submit")
        assert len(adapter.sent_messages) == 2
        assert adapter.sent_messages[1]["content"] == "Successfully posted: 201"

    asyncio.run(_run())


def test_http_module_methods(monkeypatch):
    calls = []
    def fake_sync_http(url, method="GET", headers=None, body=None, timeout=30.0):
        calls.append((method, url, body))
        return CordHttpResponse(200, '{"ok": true}', {}, url)

    import cord.runtime
    monkeypatch.setattr(cord.runtime, "_sync_http_request", fake_sync_http)

    async def _run():
        http = CordHttpModule()
        r1 = await http.get("https://api.test/get")
        r2 = await http.post("https://api.test/post", json={"a": 1})
        r3 = await http.delete("https://api.test/del")

        assert r1.status == 200
        assert calls[0][0] == "GET"
        assert calls[1][0] == "POST"
        assert calls[2][0] == "DELETE"

    asyncio.run(_run())
