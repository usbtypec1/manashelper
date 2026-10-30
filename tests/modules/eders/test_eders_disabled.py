import subprocess
import sys
from textwrap import dedent


def test_disabled_feature_has_no_entry_points_or_jobs(monkeypatch):
    # aiogram routers can only be attached once, so check startup in a fresh process.
    monkeypatch.setenv("MANASHELPER_EDERS_PASSWORD", "")
    script = dedent("""\
        from dishka import make_async_container
        from manashelper.core.config import get_settings
        from manashelper.core.provider import CoreProvider
        from manashelper.jobs.scheduler import create_scheduler
        from manashelper.localization.locale import Locale
        from manashelper.modules.eders.jobs import poll_eders_job
        from manashelper.modules.notifications.keyboards import build_notifications_keyboard
        from manashelper.modules.notifications.settings import NotificationSettingsSummary
        from manashelper.platform.i18n.catalog import i18n
        from manashelper.platform.telegram.callbacks import SettingsAction, SettingsCallback
        from manashelper.platform.telegram.command_catalog import build_private_commands
        from manashelper.platform.telegram.dispatcher import create_dispatcher
        from manashelper.platform.telegram.navigation import build_main_keyboard

        get_settings.cache_clear()
        settings = get_settings()
        assert not settings.eders_enabled
        container = make_async_container(CoreProvider())
        dispatcher = create_dispatcher(container)
        assert not {'eders', 'study_week'} & {r.name for r in dispatcher.sub_routers}
        assert all(j.func is not poll_eders_job for j in create_scheduler(container, None).get_jobs())
        with i18n.context(), i18n.use_locale('ru'):
            labels = [b.text for row in build_main_keyboard().keyboard for b in row]
            eders_keys = ('menu.eders', 'menu.eders_materials', 'menu.study_week')
            assert not any(i18n.gettext(key) in labels for key in eders_keys)
            keyboard = build_notifications_keyboard(NotificationSettingsSummary(True, True, True))
            buttons = [b for row in keyboard.inline_keyboard for b in row]
            eders_callback = SettingsCallback(action=SettingsAction.OPEN_EDERS_NOTIFICATIONS).pack()
            assert all(b.callback_data != eders_callback for b in buttons)
        commands = {c.command for c in build_private_commands(Locale.RU)}
        assert not {'eders', 'materials', 'week', 'eders_settings'} & commands
    """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
