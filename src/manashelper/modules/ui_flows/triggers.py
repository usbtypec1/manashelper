"""Initial compatibility bindings. Once initialized, operator DB documents win."""

from ui_flows.domain.ingress import LegacyTarget, ScenarioTarget, TriggerBinding, TriggerDocument

LEGACY_STATES = {
    "ObisCredentialsForm": "obis",
    "PhoneNumberForm": "phone_numbers",
    "FeedbackForm": "feedback",
    "LessonSearchForm": "lesson_search",
    "BroadcastForm": "broadcast",
    "AdvertisementForm": "advertisement",
    "AdvertisementModerationForm": "advertisement_moderation",
    "StudentQuestionsForm": "student_questions",
}

# Registered codecs are owned by their feature; settings/timetable actions have distinct owners.
CALLBACK_OWNERS = {
    "ad": "advertisement",
    "ad_delete": "advertisement",
    "ad_expiry": "advertisement",
    "ad_form": "advertisement",
    "ad_moderation": "advertisement_moderation",
    "ads_page": "advertisement",
    "broadcast": "broadcast",
    "eders": "eders",
    "eders_setting": "eders",
    "feedback": "feedback",
    "food_menu": "food_menu",
    "food_menu_date": "food_menu",
    "food_menu_open": "food_menu",
    "food_menu_rating": "food_menu",
    "food_menu_cleanup_open": "food_menu_cleanup",
    "food_menu_cleanup_set": "food_menu_cleanup",
    "food_menu_notification_bulk": "food_menu_notifications",
    "food_menu_notification_day": "food_menu_notifications",
    "food_menu_notification_meal": "food_menu_notifications",
    "food_menu_notification_noop": "food_menu_notifications",
    "food_menu_notification_weekday": "food_menu_notifications",
    "notification_setting": "notifications",
    "obis": "obis",
    "obis_results_page": "obis",
    "course": "timetable",
    "department": "timetable",
    "faculty": "timetable",
    "schedule_day": "timetable",
    "lesson_search_page": "lesson_search",
    "sqa": "student_questions",
    "sqc": "student_questions",
    "uf": "ui_flows",
    "locale": "locale",
    "theme": "theme",
    "phone_number_action": "phone_numbers",
    "phone_number_delete": "phone_numbers",
}
SETTINGS_OWNERS = {
    "open_notifications": "notifications",
    "open_eders_notifications": "eders",
    "open_food_menu_notifications": "food_menu_notifications",
    "back_to_notifications": "notifications",
    "open_course_tracking": "settings",
    "open_obis": "settings",
    "open_language": "locale",
    "open_theme": "theme",
    "open_phone_numbers": "phone_numbers",
    "open_feedback": "feedback",
    "back_to_settings": "settings",
}


def trigger_document() -> TriggerDocument:
    bindings: list[TriggerBinding] = []

    def add(id: str, kind: str, key: str, adapter: str, **values: object) -> None:
        matcher = {"kind": kind, "key": key}
        for name in ("arguments", "action"):
            if name in values:
                matcher[name] = values.pop(name)  # type: ignore[assignment]
        bindings.append(
            TriggerBinding.model_validate(
                {
                    "id": id,
                    "matcher": matcher,
                    "target": {"kind": "legacy", "adapter": adapter},
                    **values,
                }
            )
        )

    for command, adapter in {
        "language": "locale",
        "yemek": "food_menu",
        "week": "study_week",
        "eders": "eders",
        "materials": "eders",
        "eders_settings": "eders",
        "broadcast": "broadcast",
        "editor": "ui_flows",
        "flow_demo": "ui_flows",
        "hide_keyboard": "start",
    }.items():
        add(
            "cmd_" + command,
            "command",
            command,
            adapter,
            arguments="flow_id" if command == "flow_demo" else "text" if command in {"materials", "eders"} else "none",
            access="admin" if command in {"broadcast", "editor", "flow_demo"} else "public",
            policy="preserve"
            if command in {"language", "editor", "hide_keyboard"}
            else "resume"
            if command == "flow_demo"
            else "reject_if_busy",
            scope="any" if command in {"yemek", "hide_keyboard"} else "private",
            capabilities=["eders_enabled"] if adapter in {"eders", "study_week"} else [],
        )
    for key, adapter in {
        "ads.my_ads": "advertisement",
        "ads.post": "advertisement",
        "menu.attendance": "obis",
        "menu.eders": "eders",
        "menu.eders_materials": "eders",
        "menu.food": "food_menu",
        "menu.grades": "obis",
        "menu.marketplace": "advertisement",
        "menu.schedule": "timetable",
        "menu.settings": "settings",
        "menu.study_week": "study_week",
    }.items():
        add(
            "label_" + key.replace(".", "_"),
            "reply_label",
            key,
            adapter,
            scope="any" if adapter == "food_menu" else "private",
            capabilities=["eders_enabled"] if adapter in {"eders", "study_week"} else [],
        )
    for codec, adapter in CALLBACK_OWNERS.items():
        add(
            "cb_" + codec,
            "callback",
            codec,
            adapter,
            scope="any" if adapter in {"food_menu", "food_menu_cleanup", "advertisement_moderation"} else "private",
            access="admin"
            if adapter == "broadcast"
            else "moderation"
            if adapter == "advertisement_moderation"
            else "public",
            policy="preserve" if adapter in {"locale", "theme", "student_questions", "ui_flows"} else "reject_if_busy",
            capabilities=["eders_enabled"] if adapter == "eders" else [],
        )
    for action, adapter in SETTINGS_OWNERS.items():
        add(
            "set_" + action,
            "callback",
            "settings",
            adapter,
            action=action,
            policy="preserve" if adapter in {"locale", "theme"} else "reject_if_busy",
            capabilities=["eders_enabled"] if adapter == "eders" else [],
        )
    for action, adapter in {"open_my_schedule": "timetable", "open_lesson_search": "lesson_search"}.items():
        add("timetable_" + action, "callback", "timetable_menu", adapter, action=action)
    add("link_market", "deep_link", "market", "advertisement_contact")
    add("group_start", "command", "start", "start", scope="group", policy="preserve")
    add("link_ad", "prefix", "ad_", "advertisement_contact", arguments="uuid")
    add("reply_feedback", "native_reply", "feedback", "feedback", access="admin", policy="preserve")
    for id, kind, key, flow, fallback, entry, policy in (
        ("root", "command", "start", "main_menu", "start", None, "replace"),
        ("back", "reply_label", "common.back_to_menu", "main_menu", "navigation", None, "replace"),
        ("study", "reply_label", "menu.study", "main_menu", "navigation", "study", "reject_if_busy"),
        ("survey", "deep_link", "student_questions", "student_questions", "student_questions", None, "resume"),
    ):
        bindings.append(
            TriggerBinding.model_validate(
                {
                    "id": id,
                    "matcher": {"kind": kind, "key": key},
                    "target": {
                        "kind": "scenario",
                        "flow_id": flow,
                        "entry": None if id == "study" else entry,
                        "navigation": "study" if id == "study" else None,
                    },
                    "fallback_adapter": fallback,
                    "policy": policy,
                }
            )
        )
    return TriggerDocument(bindings=bindings)


def orchestration_trigger_document() -> TriggerDocument:
    """Stage-seven defaults; the original document remains the immutable compatibility catalog."""
    document = trigger_document()
    replacements = {
        "cmd_language": ("select_locale", "call", "locale"),
        "set_open_language": ("select_locale", "call", "locale"),
        "set_open_theme": ("select_theme", "call", "theme"),
        "label_menu_settings": ("settings", "replace", "settings"),
        "set_back_to_settings": ("settings", "replace", "settings"),
    }
    bindings = []
    for binding in document.bindings:
        if binding.id in replacements:
            flow_id, policy, fallback = replacements[binding.id]
            binding = TriggerBinding.model_validate(
                {
                    **binding.model_dump(),
                    "target": {"kind": "scenario", "flow_id": flow_id},
                    "policy": policy,
                    "fallback_adapter": fallback,
                }
            )
        bindings.append(binding)
    return TriggerDocument(bindings=bindings)


def legacy_adapters() -> frozenset[str]:
    return frozenset(
        [item.target.adapter for item in trigger_document().bindings if isinstance(item.target, LegacyTarget)]
        + [
            item.fallback_adapter
            for item in trigger_document().bindings
            if isinstance(item.target, ScenarioTarget) and item.fallback_adapter is not None
        ]
    )
