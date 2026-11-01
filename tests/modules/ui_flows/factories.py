import json
from dataclasses import dataclass

from manashelper.modules.student_questions.repository import StudentQuestionsRepository
from manashelper.modules.student_questions.service import StudentQuestionsService
from manashelper.modules.student_questions.survey_delegates import SurveyDelegates
from manashelper.modules.ui_flows.catalog import CATALOG_KEYS
from manashelper.modules.ui_flows.infrastructure.dialogs import DialogRepository
from manashelper.modules.ui_flows.infrastructure.flows import FlowRepository
from tests.paths import FIXTURES_DIR
from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.dialogs import DialogService
from ui_flows.application.flows import FlowService
from ui_flows.application.interpreter import FlowInterpreter
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import ButtonEvent, InputEvent
from ui_flows.domain.schema import DataField, FlowDocument
from ui_flows.domain.state import DialogState, RuntimeUser

FEATURE_IDS = frozenset(
    {
        "food_menu",
        "marketplace",
        "settings",
        "schedule",
        "study_week",
        "attendance",
        "grades",
        "eders",
        "eders_materials",
    }
)


def document(name):
    return FlowDocument.model_validate_json((FIXTURES_DIR / f"ui_flows/{name}.json").read_text(encoding="utf-8"))


def policy(*, eders_enabled=True):
    return FlowPolicy(
        CATALOG_KEYS, FEATURE_IDS, {"eders_enabled": DataField(type="boolean")}, {"eders_enabled": eders_enabled}
    )


@dataclass
class Runtime:
    flows: FlowService
    dialogs: DialogService
    registry: DelegateRegistry
    survey: StudentQuestionsService


def runtime(session, *, registry=None, runtime_policy=None):
    survey = StudentQuestionsService(StudentQuestionsRepository(session))
    registry = registry if registry is not None else SurveyDelegates(survey).registry()
    runtime_policy = runtime_policy or policy()
    flow_repository = FlowRepository(session)
    return Runtime(
        FlowService(flow_repository, registry, runtime_policy),
        DialogService(DialogRepository(session), flow_repository, FlowInterpreter(registry), runtime_policy),
        registry,
        survey,
    )


async def publish_examples(services):
    for name in ("main_menu", "student_questions"):
        await services.flows.create(document(name))
        await services.flows.publish(name, 0, 1)


def button(state: DialogState, update_id: int, button_id: str):
    return ButtonEvent(
        kind="button",
        update_id=update_id,
        user_id=state.user_id,
        chat_id=state.chat_id,
        session_id=str(state.id),
        expected_revision=state.revision,
        button_id=button_id,
    )


def entered_text(state: DialogState, update_id: int, text: str):
    return InputEvent(
        kind="input",
        update_id=update_id,
        user_id=state.user_id,
        chat_id=state.chat_id,
        session_id=str(state.id),
        expected_revision=state.revision,
        text=text,
    )


def identity(user):
    return RuntimeUser(user.id, user.id)


def delegate_definitions():
    return json.loads((FIXTURES_DIR / "ui_flows/delegates.json").read_text(encoding="utf-8"))
