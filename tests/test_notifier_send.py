import httpx
import pytest
import respx
from src.telegram_notifier import send_message


@respx.mock
def test_send_message_posts_html(capsys):
    route = respx.post("https://api.telegram.org/bot123:abc/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    send_message(token="123:abc", chat_id="999", html="<b>hi</b>", dry_run=False)
    assert route.called
    body = route.calls[0].request.read().decode()
    assert "parse_mode=HTML" in body or "parse_mode" in body
    assert "999" in body


@respx.mock
def test_send_message_dry_run_skips_http(capsys):
    route = respx.post("https://api.telegram.org/bot123:abc/sendMessage")
    send_message(token="123:abc", chat_id="999", html="<b>hi</b>", dry_run=True)
    assert not route.called
    out = capsys.readouterr().out
    assert "[DRY_RUN] Telegram" in out
    assert "hi" in out


@respx.mock
def test_send_message_raises_on_telegram_error():
    respx.post("https://api.telegram.org/bot123:abc/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False, "description": "Bad Request"})
    )
    with pytest.raises(RuntimeError, match="Telegram"):
        send_message(token="123:abc", chat_id="999", html="x", dry_run=False)
