"""ResendEmailSender request-shape test (no network; httpx.post is stubbed).

Locks the payload to Resend's send-email API. No database needed.
"""


def test_resend_sender_payload(monkeypatch):
    import httpx

    from health_shared.email import EmailMessage, ResendEmailSender

    captured: dict = {}

    class FakeResponse:
        is_error = False

        def raise_for_status(self):
            pass

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json)
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    ResendEmailSender(api_key="re_test", sender="Health <login@x.com>").send(
        EmailMessage(to="ben@example.com", subject="Login link", html="<p>hi</p>", text="hi")
    )

    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["headers"]["Authorization"] == "Bearer re_test"
    body = captured["json"]
    assert body["from"] == "Health <login@x.com>"
    assert body["to"] == ["ben@example.com"]  # Resend wants an array
    assert body["subject"] == "Login link"
    assert body["html"] == "<p>hi</p>"
    assert body["text"] == "hi"


def test_get_email_sender_defaults_to_console(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    from health_shared.email import ConsoleEmailSender, get_email_sender

    assert isinstance(get_email_sender(), ConsoleEmailSender)
