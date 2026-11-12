import io
import json

from alarmops import gitlab_api


def test_missing_env_reports_names(monkeypatch):
    for k in gitlab_api.REQUIRED_ENV:
        monkeypatch.delenv(k, raising=False)
    assert set(gitlab_api.missing_env()) == set(gitlab_api.REQUIRED_ENV)


def test_request_builds_url_and_headers(monkeypatch):
    monkeypatch.setenv("GITLAB_API_TOKEN", "tok")
    monkeypatch.setenv("CI_API_V4_URL", "https://gitlab.example/api/v4/")
    monkeypatch.setenv("CI_PROJECT_ID", "42")
    seen = {}

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=0):
        seen["url"], seen["method"] = req.full_url, req.get_method()
        seen["token"] = req.get_header("Private-token")
        seen["body"] = req.data
        return Resp(json.dumps({"id": 7}).encode())

    monkeypatch.setattr(gitlab_api.urllib.request, "urlopen", fake_urlopen)
    out = gitlab_api.request("POST", "/issues", body={"title": "t"}, query={"a": 1})
    assert out == {"id": 7}
    assert seen["url"] == "https://gitlab.example/api/v4/projects/42/issues?a=1"
    assert seen["method"] == "POST" and seen["token"] == "tok"
    assert json.loads(seen["body"]) == {"title": "t"}
