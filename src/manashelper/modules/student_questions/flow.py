"""Initial editable survey document. The public service remains the owner of answer validation/storage."""

from typing import Any

from manashelper.modules.student_questions.service import ANSWER_MAX_LENGTH, StudentCourse
from ui_flows.domain.schema import FlowDocument, Scalar

SURVEY_FLOW_ID = "student_questions"


def survey_document() -> FlowDocument:
    def text(key: str) -> dict[str, Any]:
        return {"kind": "catalog", "key": key}

    def reference(field: str, scope: str = "data") -> dict[str, str]:
        return {"kind": "ref", "scope": scope, "field": field}

    def button(id: str, key: str, target: str, **values: Scalar) -> dict[str, Any]:
        return {
            "kind": "transition",
            "id": id,
            "label": text(key),
            "target": target,
            "assignments": {name: {"kind": "literal", "value": value} for name, value in values.items()},
        }

    def cancel() -> list[dict[str, Any]]:
        return [button("cancel", "common.cancel", "cancel")]

    def menu(id: str, key: str, buttons: list[list[dict[str, Any]]]) -> dict[str, Any]:
        return {"kind": "menu", "id": id, "text": [text(key)], "keyboard": "inline", "buttons": buttons + [cancel()]}

    def yes(field: str) -> dict[str, Any]:
        return {
            "kind": "compare",
            "left": reference(field),
            "operator": "eq",
            "right": {"kind": "literal", "value": True},
        }

    def input_node(id: str, key: str, next: str) -> dict[str, Any]:
        return {
            "kind": "input",
            "id": id,
            "text": [text(key)],
            "field": id,
            "input_type": "text",
            "next": next,
            "max_length": ANSWER_MAX_LENGTH,
            "error": {
                **text("student_questions.invalid_text"),
                "parameters": {"max": {"kind": "literal", "value": ANSWER_MAX_LENGTH}},
            },
            "buttons": [cancel()],
        }

    courses = [
        button(id, "student_questions." + id, "search", course=course.value)
        for course, id in zip(
            StudentCourse, ("preparatory", "year_1", "year_2", "year_3", "year_4", "year_5", "not_student"), strict=True
        )
    ]
    course = menu("course", "student_questions.course_prompt", [[courses[0]], courses[1:4], courses[4:6], [courses[6]]])
    course["text"].insert(0, text("student_questions.intro"))
    nodes: list[dict[str, Any]] = [
        {
            "kind": "action",
            "id": "check_submission",
            "delegate": "student_questions.has_submitted",
            "arguments": {"user_id": reference("id", "user")},
            "results": {"submitted": "has_submitted"},
            "outcomes": {"success": "choose_start"},
        },
        {
            "kind": "condition",
            "id": "choose_start",
            "branches": [{"when": yes("has_submitted"), "target": "overwrite"}],
            "default": "course",
        },
        menu(
            "overwrite",
            "student_questions.already_completed",
            [
                [
                    button(
                        "replace",
                        "student_questions.fill_again",
                        "course",
                        overwrite=True,
                        questions=None,
                        found_answers=None,
                        answer_sources=None,
                    )
                ]
            ],
        ),
        course,
        menu(
            "search",
            "student_questions.search_prompt",
            [
                [
                    button("yes", "student_questions.yes", "questions", had_questions=True),
                    button(
                        "no",
                        "student_questions.no",
                        "beta",
                        had_questions=False,
                        questions=None,
                        found_answers=None,
                        answer_sources=None,
                    ),
                ]
            ],
        ),
        input_node("questions", "student_questions.questions_prompt", "found"),
        menu(
            "found",
            "student_questions.found_prompt",
            [
                [
                    button("yes", "student_questions.yes", "answer_sources", found_answers=True),
                    button("no", "student_questions.no", "beta", found_answers=False, answer_sources=None),
                ]
            ],
        ),
        input_node("answer_sources", "student_questions.sources_prompt", "beta"),
        menu(
            "beta",
            "student_questions.beta_prompt",
            [
                [
                    button("yes", "student_questions.yes", "submit", wants_beta=True),
                    button("no", "student_questions.no", "submit", wants_beta=False),
                ]
            ],
        ),
        {
            "kind": "action",
            "id": "submit",
            "delegate": "student_questions.submit",
            "arguments": {
                **{
                    name: reference(name)
                    for name in (
                        "course",
                        "overwrite",
                        "had_questions",
                        "questions",
                        "found_answers",
                        "answer_sources",
                        "wants_beta",
                    )
                },
                "user_id": reference("id", "user"),
            },
            "outcomes": {"success": "choose_thanks", "already_submitted": "overwrite"},
        },
        {
            "kind": "condition",
            "id": "choose_thanks",
            "branches": [{"when": yes("wants_beta"), "target": "thanks_beta"}],
            "default": "thanks",
        },
        *(
            {"kind": "end", "id": id, "status": status, "text": [text(key) for key in keys], "return_flow": "main_menu"}
            for id, status, keys in (
                ("thanks", "completed", ["student_questions.thanks"]),
                ("thanks_beta", "completed", ["student_questions.thanks", "student_questions.beta_follow_up"]),
                ("cancel", "cancelled", ["student_questions.cancelled"]),
            )
        ),
    ]
    fields: dict[str, dict[str, Any]] = {
        name: {"type": "boolean"} for name in ("has_submitted", "overwrite", "had_questions", "wants_beta")
    }
    fields.update(
        {
            "course": {"type": "text"},
            "questions": {"type": "text", "nullable": True},
            "found_answers": {"type": "boolean", "nullable": True},
            "answer_sources": {"type": "text", "nullable": True},
        }
    )
    return FlowDocument.model_validate(
        {
            "schema_version": 1,
            "id": SURVEY_FLOW_ID,
            "entry": "check_submission",
            "fields": fields,
            "initial_data": {"overwrite": False, "questions": None, "found_answers": None, "answer_sources": None},
            "nodes": nodes,
            "layout": {
                node["id"]: {"x": 80 + (index % 3) * 360, "y": 80 + (index // 3) * 340}
                for index, node in enumerate(nodes)
            },
        }
    )
