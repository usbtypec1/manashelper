"""Export Mini App boot/error copy from the same catalogs as the bot."""

import json
from gettext import NullTranslations
from pathlib import Path

from babel.messages.pofile import read_po

from manashelper.localization.theme import Theme
from manashelper.platform.legal import TERMS_SOURCES, TERMS_UPDATED

ROOT = Path(__file__).resolve().parents[2]

# Mark client-only strings for Babel and resolve them from each catalog below.
_ = NullTranslations().gettext
ADMIN_MESSAGES = (
    _("miniapp.admin.title"),
    _("miniapp.admin.users"),
    _("miniapp.admin.name"),
    _("miniapp.admin.denied"),
    _("miniapp.admin.empty"),
    _("miniapp.admin.load_more"),
    _("miniapp.admin.refresh"),
    _("miniapp.admin.active"),
    _("miniapp.admin.stopped"),
    _("miniapp.admin.filters"),
    _("miniapp.admin.search"),
    _("miniapp.admin.search_hint"),
    _("miniapp.admin.language"),
    _("miniapp.admin.theme"),
    _("miniapp.admin.status"),
    _("miniapp.admin.any_language"),
    _("miniapp.admin.any_theme"),
    _("miniapp.admin.any_status"),
    _("miniapp.admin.no_matches"),
    _("miniapp.admin.broadcasts"),
    _("miniapp.admin.broadcast"),
    _("miniapp.admin.new_broadcast"),
    _("miniapp.admin.audience"),
    _("miniapp.admin.all"),
    _("miniapp.admin.allowlist"),
    _("miniapp.admin.blocklist"),
    _("miniapp.admin.pick_users"),
    _("miniapp.admin.search_results"),
    _("miniapp.admin.selected_count"),
    _("miniapp.admin.remove_user"),
    _("miniapp.admin.eligibility"),
    _("miniapp.admin.variants"),
    _("miniapp.admin.fallback"),
    _("miniapp.admin.message"),
    _("miniapp.admin.add_variant"),
    _("miniapp.admin.remove_variant"),
    _("miniapp.admin.duplicate_variant"),
    _("miniapp.admin.queue"),
    _("miniapp.admin.confirm_all"),
    _("miniapp.admin.confirm_allowlist"),
    _("miniapp.admin.confirm_blocklist"),
    _("miniapp.admin.invalid_broadcast"),
    _("miniapp.admin.no_broadcasts"),
    _("miniapp.admin.no_recipients"),
    _("miniapp.admin.deliveries"),
    _("miniapp.admin.attempts"),
    _("miniapp.admin.pending"),
    _("miniapp.admin.processing"),
    _("miniapp.admin.sent"),
    _("miniapp.admin.failed"),
    _("miniapp.admin.expired"),
    _("miniapp.admin.cancelled"),
    _("miniapp.admin.retry_deliveries"),
    _("miniapp.admin.confirm_retry"),
    _("miniapp.admin.retried_count"),
    _("miniapp.admin.none_retried"),
)

messages = {}
for locale in ("en", "ru", "ky", "tr", "zh"):
    with (ROOT / f"src/manashelper/locales/{locale}/LC_MESSAGES/messages.po").open(encoding="utf-8") as stream:
        catalog = read_po(stream)
    messages[locale] = {
        str(message.id).removeprefix("gamification.ui."): message.string
        for message in catalog
        if isinstance(message.id, str) and message.id.startswith("gamification.ui.")
    }
    messages[locale]["preferences"] = {
        str(message.id).removeprefix("miniapp.ui."): message.string
        for message in catalog
        if isinstance(message.id, str) and message.id.startswith("miniapp.ui.")
    }
    messages[locale]["admin"] = {key.removeprefix("miniapp.admin."): catalog[key].string for key in ADMIN_MESSAGES}
    messages[locale]["adminThemes"] = {theme.value: catalog[f"theme.{theme.value}"].string for theme in Theme}
    messages[locale]["terms"] = {
        str(message.id).removeprefix("terms."): message.string
        for message in catalog
        if isinstance(message.id, str) and message.id.startswith("terms.")
    }
    messages[locale]["terms"]["sources"] = TERMS_SOURCES
    messages[locale]["terms"]["updated"] = TERMS_UPDATED
target = ROOT / "frontend/src/messages.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(messages, ensure_ascii=False) + "\n", encoding="utf-8")
