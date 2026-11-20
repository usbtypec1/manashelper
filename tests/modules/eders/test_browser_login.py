from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import httpx
import pytest
from aiogram.types import CallbackQuery, Message
from pydantic import SecretStr

from manashelper.core.config import Settings
from manashelper.localization.locale import Locale
from manashelper.localization.theme import Theme
from manashelper.modules.eders.application.browser_login import EdersLoginTokens
from manashelper.modules.eders.application.tracking import EdersEvent
from manashelper.modules.eders.application.use_cases.issue_eders_login_link import IssueEdersLoginLinkUseCase
from manashelper.modules.eders.application.use_cases.redeem_eders_login_link import RedeemEdersLoginLinkUseCase
from manashelper.modules.eders.errors import EdersFetchError, EdersUnsafeUrlError, InvalidEdersLoginLinkError
from manashelper.modules.eders.infrastructure import client as client_module
from manashelper.modules.eders.infrastructure.client import browser_sso_url
from manashelper.modules.eders.presentation import keyboards
from manashelper.modules.eders.presentation.callbacks import EdersAction, EdersCompletionCallback, EdersMenuCallback
from manashelper.modules.eders.presentation.router import on_eders_completion, on_eders_login
from manashelper.modules.eders.presentation.sender import TelegramEdersNotificationSender
from manashelper.modules.obis.application.models import StoredCredentials
from manashelper.modules.obis.errors import ObisSessionExpiredError, UserHasNoCredentialsError, UserNotFoundError
from manashelper.platform.i18n.catalog import i18n
from tests.modules.eders.factories import item, make_eders_client


def settings():
    return Settings.model_construct(public_url="https://bot.example.com", eders_password=SecretStr("fake-password"))


def test_grants_are_single_use_and_new_link_revokes_previous(monkeypatch):
    monkeypatch.setattr("manashelper.modules.eders.application.browser_login.time.monotonic", lambda: 100)
    tokens = EdersLoginTokens()
    old = tokens.issue(42, "marker")
    other = tokens.issue(43, "other")
    latest = tokens.issue(42, "marker")
    with pytest.raises(InvalidEdersLoginLinkError):
        tokens.consume(old)
    assert tokens.consume(other).user_id == 43
    assert tokens.consume(latest).user_id == 42
    with pytest.raises(InvalidEdersLoginLinkError):
        tokens.consume(latest)
    expired = tokens.issue(42, "marker")
    monkeypatch.setattr("manashelper.modules.eders.application.browser_login.time.monotonic", lambda: 160)
    with pytest.raises(InvalidEdersLoginLinkError):
        tokens.consume(expired)


@pytest.mark.parametrize("token", ["", "a" * 42, "a" * 44, "a" * 42 + "é", "a" * 42 + "/"])
def test_invalid_grants_are_rejected(token):
    with pytest.raises(InvalidEdersLoginLinkError):
        EdersLoginTokens().consume(token)


@pytest.mark.parametrize(
    "changed",
    [None, StoredCredentials(None, None), StoredCredentials("other", "cipher"), StoredCredentials("student", "new")],
)
async def test_changed_or_removed_credentials_revoke_link_before_upstream_access(changed):
    original = StoredCredentials("student", "cipher")
    store = AsyncMock(get_by_user_id=AsyncMock(return_value=original))
    tokens = EdersLoginTokens()
    url = await IssueEdersLoginLinkUseCase(store, tokens, settings()).execute(42, Locale.RU)
    assert original.student_number not in url and original.encrypted_password not in url
    assert urlsplit(url).query == "lang=ru"
    store.get_by_user_id.return_value = changed
    access, client = AsyncMock(), AsyncMock()
    users = AsyncMock(is_blocked=AsyncMock(return_value=False))
    redeem = RedeemEdersLoginLinkUseCase(store, tokens, client, access, users)
    with pytest.raises(InvalidEdersLoginLinkError):
        await redeem.execute(urlsplit(url).fragment)
    store.lock.assert_awaited_once_with(42)
    access.with_session.assert_not_awaited()
    client.create_browser_login_url.assert_not_awaited()


@pytest.mark.parametrize(
    "stored,error", [(None, UserNotFoundError), (StoredCredentials(None, None), UserHasNoCredentialsError)]
)
async def test_unknown_or_unlinked_user_cannot_issue_link(stored, error):
    store = AsyncMock(get_by_user_id=AsyncMock(return_value=stored))
    with pytest.raises(error):
        await IssueEdersLoginLinkUseCase(store, EdersLoginTokens(), settings()).execute(42, Locale.RU)


@pytest.mark.parametrize("redirect", [True, False])
async def test_browser_sso_is_not_consumed_by_backend_and_preserves_cookie_rotation(monkeypatch, redirect):
    requests = []
    url = "https://eders.manas.edu.kg/auth/userkey/login.php?key=fake-sso"

    def handle(request):
        requests.append(request)
        assert request.url.host == "obistest.manas.edu.kg" and request.url.path == "/site/eders"
        assert request.headers["cookie"] == "obis=secret"
        if redirect:
            return httpx.Response(302, headers={"location": url, "set-cookie": "obis=rotated; Path=/"})
        return httpx.Response(200, text=f'<a href="{url}">Eders</a>', headers={"set-cookie": "obis=rotated; Path=/"})

    monkeypatch.setattr(
        client_module, "new_http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handle))
    )
    cookies = {"obis": "secret"}
    assert await make_eders_client().create_browser_login_url(cookies) == url
    assert len(requests) == 1 and cookies == {"obis": "rotated"}


@pytest.mark.parametrize(
    "url",
    [
        "https://[invalid/auth/userkey/login.php?key=fake",
        "http://eders.manas.edu.kg/auth/userkey/login.php?key=fake",
        "https://evil.example/auth/userkey/login.php?key=fake",
        "https://eders.manas.edu.kg.evil.example/auth/userkey/login.php?key=fake",
        "https://user@eders.manas.edu.kg/auth/userkey/login.php?key=fake",
        "https://eders.manas.edu.kg:444/auth/userkey/login.php?key=fake",
        "https://eders.manas.edu.kg/login/index.php?key=fake",
        "https://eders.manas.edu.kg/auth/userkey/login.php?key=",
        "https://eders.manas.edu.kg/auth/userkey/login.php?key=fake&key=",
        "https://eders.manas.edu.kg/auth/userkey/login.php?key=fake#fragment",
    ],
)
def test_browser_sso_rejects_untrusted_destinations(url):
    with pytest.raises(EdersUnsafeUrlError):
        browser_sso_url(url)


def test_browser_sso_drops_untrusted_onward_redirect():
    assert browser_sso_url(
        "https://eders.manas.edu.kg/auth/userkey/login.php?key=fake&wantsurl=https://evil.example"
    ) == ("https://eders.manas.edu.kg/auth/userkey/login.php?key=fake")


@pytest.mark.parametrize(
    "status,body,headers",
    [(302, "", {"location": "/site/login?next=eders"}), (200, '<input name="LoginForm[username]">', {})],
)
async def test_browser_sso_reports_expired_obis_session(monkeypatch, status, body, headers):
    transport = httpx.MockTransport(lambda request: httpx.Response(status, text=body, headers=headers))
    monkeypatch.setattr(client_module, "new_http_client", lambda: httpx.AsyncClient(transport=transport))
    with pytest.raises(ObisSessionExpiredError):
        await make_eders_client().create_browser_login_url({"obis": "secret"})


@pytest.mark.parametrize("chat_id", [42, 999])
async def test_callback_issues_only_for_owner_in_private_chat(chat_id):
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = SimpleNamespace(id=42)
    callback.message = AsyncMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.message.chat = SimpleNamespace(id=chat_id)
    issue = AsyncMock(execute=AsyncMock(return_value="https://bot.example.com/api/eders/browser-login#fake"))
    with i18n.context(), i18n.use_locale("ru"):
        await on_eders_login(callback, issue)
    if chat_id != 42:
        issue.execute.assert_not_awaited()
        callback.message.answer.assert_not_awaited()
    else:
        issue.execute.assert_awaited_once_with(42, Locale.RU)
        assert callback.message.answer.call_args.kwargs["protect_content"] is True


async def test_disabled_browser_login_does_not_issue_grant():
    config = settings()
    config.public_url = None
    with pytest.raises(EdersFetchError):
        await IssueEdersLoginLinkUseCase(AsyncMock(), EdersLoginTokens(), config).execute(42, Locale.RU)


@pytest.mark.parametrize("locale", list(Locale))
@pytest.mark.parametrize("manual,event_type", [(True, "before_2"), (False, "before_2"), (False, "material_new")])
async def test_all_notification_types_have_localized_login_with_existing_completion(
    locale, manual, event_type, monkeypatch
):
    monkeypatch.setattr(keyboards, "get_settings", settings)
    now = datetime.now(UTC)
    activity = item(manual_completion=manual, closes=replace(item().closes, instant=now + timedelta(hours=2)))
    event = EdersEvent("key", activity, event_type, now, now)
    outbox = AsyncMock(enqueue=AsyncMock(return_value=True))
    themes = AsyncMock(get_theme=AsyncMock(return_value=Theme.BASIC))
    assert [sent async for sent in TelegramEdersNotificationSender(outbox, themes).send(42, locale, [event])] == [event]
    message = outbox.enqueue.call_args.args[1][0]
    buttons = [button for row in message.reply_markup.inline_keyboard for button in row]
    login = buttons[-1]
    assert login.text == i18n.gettext("eders.quick_login", locale=locale.value)
    assert EdersMenuCallback.unpack(login.callback_data).action == EdersAction.LOGIN
    assert login.url is None
    if manual:
        assert EdersCompletionCallback.unpack(buttons[0].callback_data).activity_id == activity.id


async def test_completion_edit_preserves_login_button(monkeypatch):
    monkeypatch.setattr(keyboards, "get_settings", settings)
    callback = AsyncMock(spec=CallbackQuery)
    callback.answer = AsyncMock()
    callback.from_user = SimpleNamespace(id=42)
    callback.message = AsyncMock(spec=Message)
    callback.message.chat = SimpleNamespace(id=42)
    callback.message.text = "Reminder"
    callback.message.html_text = "<b>Reminder</b>"
    callback.message.edit_text = AsyncMock()
    with i18n.context(), i18n.use_locale("ru"):
        await on_eders_completion(callback, EdersCompletionCallback(activity_id=20, completed=True), AsyncMock())
    buttons = callback.message.edit_text.call_args.kwargs["reply_markup"].inline_keyboard
    assert EdersCompletionCallback.unpack(buttons[0][0].callback_data).completed is False
    assert EdersMenuCallback.unpack(buttons[1][0].callback_data).action == EdersAction.LOGIN
