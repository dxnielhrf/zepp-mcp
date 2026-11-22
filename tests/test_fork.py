"""Guards for the hardened fork."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from zepp_mcp import auth, server
from zepp_mcp import client as api
from zepp_mcp import login as login_cli


def _tool_names() -> set[str]:
    return {t.name for t in asyncio.run(server.server.list_tools())}


def test_raw_request_tool_is_not_exposed():
    names = _tool_names()
    assert "zepp_raw_request" not in names
    assert len(names) == 13


# -- token-only mode (no ZEPP_PASSWORD) ---------------------------------------

def _client(monkeypatch, tmp_path, status: int):
    monkeypatch.setenv("ZEPP_TOKEN_CACHE", str(tmp_path / "token.json"))
    monkeypatch.delenv("ZEPP_EMAIL", raising=False)
    monkeypatch.delenv("ZEPP_PASSWORD", raising=False)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(status, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return api.ZeppClient(None, None, "DE", http=http, min_interval=0,
                          cache=False), seen


def _cache_token():
    auth.save_cached(auth.Credential(
        app_token="t", user_id="1", region_host="api-mifit-de2.zepp.com",
        country_code="DE", expires_at=time.time() + 30 * 86400))


def test_from_env_needs_no_credentials(monkeypatch):
    monkeypatch.delenv("ZEPP_EMAIL", raising=False)
    monkeypatch.delenv("ZEPP_PASSWORD", raising=False)
    assert isinstance(api.from_env(), api.ZeppClient)


def test_no_token_and_no_password_never_logs_in(monkeypatch, tmp_path):
    client, seen = _client(monkeypatch, tmp_path, 200)
    with pytest.raises(auth.LoginError, match="zepp-login"):
        client.credential()
    assert seen == []


def test_401_in_token_only_mode_keeps_token_and_skips_login(monkeypatch, tmp_path):
    client, seen = _client(monkeypatch, tmp_path, 401)
    _cache_token()
    outcome = client.get("/v1/data/band_data.json", {})
    assert outcome.http_status == 401 and outcome.status == "error"
    assert seen == ["api-mifit-de2.zepp.com"]          # one data call, no auth host
    assert (tmp_path / "token.json").is_file()


# -- zepp-login ----------------------------------------------------------------

def _login_env(monkeypatch, tmp_path, fake_login):
    monkeypatch.setenv("ZEPP_TOKEN_CACHE", str(tmp_path / "token.json"))
    monkeypatch.setenv("ZEPP_EMAIL", "a@example.com")
    monkeypatch.setattr(login_cli.getpass, "getpass", lambda prompt: "pw")
    calls: list[str] = []

    def counting(http, email, password, country):
        calls.append(email)
        return fake_login()

    monkeypatch.setattr(login_cli.auth, "login", counting)
    return calls


def test_zepp_login_stores_token_after_one_attempt(monkeypatch, tmp_path, capsys):
    calls = _login_env(monkeypatch, tmp_path, lambda: auth.Credential(
        app_token="secret-token", user_id="1", region_host="api-mifit-de2.zepp.com",
        country_code="DE", expires_at=time.time() + 30 * 86400))
    assert login_cli.main() == 0
    assert calls == ["a@example.com"]
    assert auth.load_cached().app_token == "secret-token"
    assert (tmp_path / "token.json").stat().st_mode & 0o777 == 0o600
    out = capsys.readouterr()
    assert "secret-token" not in out.out + out.err and "pw" not in out.out


def test_zepp_login_failure_is_not_retried(monkeypatch, tmp_path):
    def reject():
        raise auth.LoginError("rejected")

    calls = _login_env(monkeypatch, tmp_path, reject)
    assert login_cli.main() == 1
    assert len(calls) == 1
    assert not (tmp_path / "token.json").exists()


# -- automatic login with stored credentials ---------------------------------


def test_credentials_file_enables_login(monkeypatch, tmp_path):
    creds = tmp_path / "credentials"
    creds.write_text("a@example.com\np@ss word$\n")
    monkeypatch.delenv("ZEPP_EMAIL", raising=False)
    monkeypatch.delenv("ZEPP_PASSWORD", raising=False)
    monkeypatch.setenv("ZEPP_CREDENTIALS_FILE", str(creds))
    client = api.from_env()
    assert client.can_login
    assert client._password == "p@ss word$"


def test_rejected_auto_login_blocks_further_attempts(monkeypatch, tmp_path):
    monkeypatch.setenv("ZEPP_TOKEN_CACHE", str(tmp_path / "token.json"))
    attempts: list[int] = []

    def reject(*args, **kwargs):
        attempts.append(1)
        raise auth.LoginError("rejected")

    monkeypatch.setattr(api, "login", reject)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(401)))
    client = api.ZeppClient("a@example.com", "wrong", "DE", http=http,
                            min_interval=0, cache=False)
    _cache_token()
    assert client.get("/v1/data/band_data.json", {}).http_status == 401
    for _ in range(3):
        with pytest.raises(auth.LoginError, match="blocked"):
            client.get("/v1/data/band_data.json", {})
    assert len(attempts) == 1                      # never more than one try
    assert auth.login_blocked() == "rejected"
    fresh = api.ZeppClient("a@example.com", "wrong", "DE", http=http,
                           min_interval=0, cache=False)
    with pytest.raises(auth.LoginError, match="blocked"):
        fresh.credential()                         # survives a restart
    assert len(attempts) == 1


def test_zepp_login_clears_the_block(monkeypatch, tmp_path):
    _login_env(monkeypatch, tmp_path, lambda: auth.Credential(
        app_token="t", user_id="1", region_host="h", country_code="DE",
        expires_at=time.time() + 86400))
    auth.block_login("rejected")
    assert login_cli.main() == 0
    assert auth.login_blocked() is None
