from types import SimpleNamespace
from unittest import mock

import pytest
from fastmcp.exceptions import ToolError

import oauth


def test_no_client_id_means_no_auth(monkeypatch):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    assert oauth.build_auth() is None


def test_current_user_requires_token():
    with mock.patch("oauth.get_access_token", return_value=None):
        with pytest.raises(ToolError):
            oauth.current_user()


def test_current_user_reads_google_claims():
    tok = SimpleNamespace(claims={"sub": "123", "email": "a@b.co"})
    with mock.patch("oauth.get_access_token", return_value=tok):
        assert oauth.current_user() == oauth.User("123", "a@b.co")


def test_email_includes_signed_in_user(monkeypatch):
    import main

    monkeypatch.setattr(main, "auth", object())  # pretend auth is enabled
    monkeypatch.setattr(main, "RESEND_API_KEY", "k")
    tok = SimpleNamespace(claims={"sub": "123", "email": "a@b.co"})
    with mock.patch("oauth.get_access_token", return_value=tok), mock.patch(
        "httpx.post"
    ) as post:
        main.send_question_email("hi", "Al", "a@b.co")
    assert "Signed in: a@b.co (Google)" in post.call_args.kwargs["json"]["text"]


def test_email_tool_rejects_unauthenticated_when_auth_enabled(monkeypatch):
    import main

    monkeypatch.setattr(main, "auth", object())
    with mock.patch("oauth.get_access_token", return_value=None):
        with pytest.raises(ToolError):
            main.send_question_email("hi", "Al", "a@b.co")
