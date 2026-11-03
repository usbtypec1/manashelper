"""Explicit adapters to the survey's public service, sharing its REQUEST transaction."""

from collections.abc import Mapping
from typing import cast

from manashelper.modules.student_questions.service import (
    AlreadySubmittedError,
    StudentCourse,
    StudentQuestionsAnswers,
    StudentQuestionsService,
)
from ui_flows.application.delegates import DelegateBinding, DelegateRegistry
from ui_flows.domain.contracts import (
    DelegateContext,
    DelegateDefinition,
    DelegateParameter,
    DelegateResult,
)
from ui_flows.domain.schema import DataField, DataValue
from ui_flows.errors import FlowExecutionError


class SurveyDelegates:
    def __init__(self, service: StudentQuestionsService) -> None:
        self._service = service

    @staticmethod
    def _check_user(context: DelegateContext, arguments: Mapping[str, DataValue]) -> None:
        if arguments["user_id"] != context.user_id:
            raise FlowExecutionError("Survey delegate cannot act for another user")

    async def has_submitted(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        self._check_user(context, arguments)
        return DelegateResult("success", {"submitted": await self._service.has_submitted(context.user_id)})

    async def submit(self, context: DelegateContext, arguments: Mapping[str, DataValue]) -> DelegateResult:
        self._check_user(context, arguments)
        answers = StudentQuestionsAnswers(
            course=StudentCourse(cast(str, arguments["course"])),
            had_questions=cast(bool, arguments["had_questions"]),
            questions=cast(str | None, arguments["questions"]),
            found_answers=cast(bool | None, arguments["found_answers"]),
            answer_sources=cast(str | None, arguments["answer_sources"]),
            wants_beta=cast(bool, arguments["wants_beta"]),
        )
        try:
            await self._service.submit(context.user_id, answers, overwrite=cast(bool, arguments["overwrite"]))
        except AlreadySubmittedError:
            return DelegateResult("already_submitted", {})
        return DelegateResult("success", {})

    def registry(self) -> DelegateRegistry:
        return DelegateRegistry(
            [
                DelegateBinding(
                    DelegateDefinition(
                        id="student_questions.has_submitted",
                        effect="read",
                        inputs={"user_id": DelegateParameter(type="integer")},
                        outputs={"submitted": DataField(type="boolean")},
                        outcomes=["success"],
                    ),
                    self.has_submitted,
                ),
                DelegateBinding(
                    DelegateDefinition(
                        id="student_questions.submit",
                        effect="database_write",
                        inputs={
                            "user_id": DelegateParameter(type="integer"),
                            "course": DelegateParameter(type="text"),
                            "had_questions": DelegateParameter(type="boolean"),
                            "overwrite": DelegateParameter(type="boolean"),
                            "questions": DelegateParameter(type="text", nullable=True),
                            "found_answers": DelegateParameter(type="boolean", nullable=True),
                            "answer_sources": DelegateParameter(type="text", nullable=True),
                            "wants_beta": DelegateParameter(type="boolean"),
                        },
                        outcomes=["success", "already_submitted"],
                    ),
                    self.submit,
                ),
            ]
        )
