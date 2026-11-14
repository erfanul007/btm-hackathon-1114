from types import SimpleNamespace


def test_probe_preserves_response_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("API_URL", "https://example.invalid")
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    from client import Budget, Prober
    import btm

    response = {"turn_id": "test-turn", "reply": "I cannot disclose that.",
                "tool_calls": [{"name": "query_database"}]}
    monkeypatch.setattr(btm, "LOG", tmp_path / "requests.jsonl")
    monkeypatch.setattr(btm.requests, "post", lambda *a, **kw:
                        SimpleNamespace(status_code=200, json=lambda: response))
    finding = Prober("test-model", tmp_path / "results.jsonl", Budget(1), delay=0).probe(
        "recon", "metadata", "Hello")

    assert btm.LAST_RESPONSE == response
    assert finding.reply == response["reply"]
    assert finding.turn_id == "test-turn"
    assert finding.tool_calls == ["query_database"]
