import ast
import importlib
import re
from dataclasses import is_dataclass

from tests.paths import PROJECT_ROOT

MODULES = PROJECT_ROOT / "src/manashelper/modules"


def test_application_dependencies_are_frozen_slotted_dataclasses():
    checked = []
    for path in MODULES.rglob("*.py"):
        relative = path.relative_to(MODULES)
        if "application" not in relative.parts and path.name not in {"service.py", "queries.py", "settings.py"}:
            continue
        tree = ast.parse(path.read_text())
        names = [
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.endswith(("UseCase", "Query", "Service"))
        ]
        if not names:
            continue
        module_name = ".".join(path.relative_to(PROJECT_ROOT / "src").with_suffix("").parts)
        if module_name.endswith(".__init__"):
            module_name = module_name.removesuffix(".__init__")
        module = importlib.import_module(module_name)
        for name in names:
            cls = getattr(module, name)
            assert is_dataclass(cls), f"{path}: {name} must be a dataclass"
            assert cls.__dataclass_params__.frozen, f"{path}: {name} must be frozen"
            assert "__slots__" in vars(cls), f"{path}: {name} must define slots"
            checked.append(name)
    assert checked


def test_use_cases_follow_file_class_and_entry_point_conventions():
    checked_modules = set()
    for path in MODULES.glob("*/application/use_cases/*.py"):
        if path.name == "__init__.py":
            continue
        classes = [node for node in ast.parse(path.read_text()).body if isinstance(node, ast.ClassDef)]
        assert len(classes) == 1, path
        cls = classes[0]
        assert cls.name.endswith("UseCase"), path
        action = cls.name.removesuffix("UseCase")
        assert path.stem == re.sub(r"(?<!^)(?=[A-Z])", "_", action).lower(), path
        methods = [
            node.name
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
        ]
        assert methods == ["execute"], f"{path}: only execute is a public entry point"
        checked_modules.add(path.relative_to(MODULES).parts[0])
    expected_modules = {
        path.name for path in MODULES.iterdir() if (path / "__init__.py").is_file() and not path.name.startswith("_")
    }
    assert checked_modules == expected_modules


def test_internal_cross_module_imports_do_not_use_private_symbols():
    violations = []
    for root in (PROJECT_ROOT / "src/manashelper", PROJECT_ROOT / "tests"):
        for path in root.rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if not node.module.startswith(("manashelper.", "tests.")):
                    continue
                for name in node.names:
                    if name.name.startswith("_"):
                        violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: {name.name}")
    assert violations == []


async def test_all_use_cases_resolve_in_independent_request_scopes():
    from unittest.mock import AsyncMock

    from dishka import make_async_container

    from manashelper.core.provider import CoreProvider
    from manashelper.modules.advertisements.application.expiry import PublicationRemover
    from manashelper.modules.advertisements.provider import AdvertisementsProvider
    from manashelper.modules.broadcast.provider import BroadcastProvider
    from manashelper.modules.eders.provider import EdersProvider
    from manashelper.modules.feedback.provider import FeedbackProvider
    from manashelper.modules.food_menu.provider import FoodMenuProvider
    from manashelper.modules.gamification.provider import GamificationProvider
    from manashelper.modules.notifications.provider import NotificationsProvider
    from manashelper.modules.obis.provider import ObisProvider
    from manashelper.modules.schedule.provider import ScheduleProvider
    from manashelper.modules.study_week.provider import StudyWeekProvider
    from manashelper.modules.users.provider import UsersProvider
    from manashelper.platform.telegram.outbox.provider import OutboxProvider

    cases = []
    for path in MODULES.glob("*/application/use_cases/*.py"):
        if path.name == "__init__.py":
            continue
        module_name = ".".join(path.relative_to(PROJECT_ROOT / "src").with_suffix("").parts)
        module = importlib.import_module(module_name)
        cases.extend(
            getattr(module, node.name)
            for node in ast.parse(path.read_text()).body
            if isinstance(node, ast.ClassDef) and node.name.endswith("UseCase")
        )
    providers = (
        CoreProvider(),
        AdvertisementsProvider(),
        BroadcastProvider(),
        EdersProvider(),
        FeedbackProvider(),
        FoodMenuProvider(),
        GamificationProvider(),
        NotificationsProvider(),
        ObisProvider(),
        ScheduleProvider(),
        StudyWeekProvider(),
        UsersProvider(),
        OutboxProvider(),
    )
    context = {PublicationRemover: AsyncMock(spec=PublicationRemover)}
    async with make_async_container(*providers) as container:
        async with container(context=context) as request:
            first = [await request.get(case) for case in cases]
            for case, instance in zip(cases, first, strict=True):
                assert await request.get(case) is instance
        async with container(context=context) as request:
            for case, instance in zip(cases, first, strict=True):
                assert await request.get(case) is not instance
