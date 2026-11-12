import httpx
import pytest
from openai import APITimeoutError, InternalServerError, BadRequestError

import llm
from schemas import IntakeResult


class _Msg:
    def __init__(self, content): self.content = content


class _Choice:
    def __init__(self, content): self.message = _Msg(content)


class _Resp:
    usage = None
    def __init__(self, content): self.choices = [_Choice(content)]


def _fake_client(monkeypatch, outcomes):
    calls = {"n": 0}

    class C:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    o = outcomes[min(calls["n"], len(outcomes) - 1)]
                    calls["n"] += 1
                    if isinstance(o, Exception):
                        raise o
                    return _Resp(o)

    monkeypatch.setattr(llm, "client", C)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return calls


GOOD = '{"summary": "s", "indicators": {}, "search_queries": []}'
REQ = httpx.Request("POST", "http://x")


def test_retries_once_after_timeout(monkeypatch):
    calls = _fake_client(monkeypatch, [APITimeoutError(request=REQ), GOOD])
    out, _ = llm.call_json("m", "sys", "user", IntakeResult)
    assert out.summary == "s" and calls["n"] == 2


def test_retries_once_after_503_then_gives_up(monkeypatch):
    resp = httpx.Response(503, request=REQ)
    err = InternalServerError("busy", response=resp, body=None)
    calls = _fake_client(monkeypatch, [err, err])
    with pytest.raises(InternalServerError):
        llm.call_json("m", "sys", "user", IntakeResult)
    assert calls["n"] == 2


def test_client_errors_are_not_retried(monkeypatch):
    resp = httpx.Response(400, request=REQ)
    err = BadRequestError("bad", response=resp, body=None)
    calls = _fake_client(monkeypatch, [err, GOOD])
    with pytest.raises(BadRequestError):
        llm.call_json("m", "sys", "user", IntakeResult)
    assert calls["n"] == 1
