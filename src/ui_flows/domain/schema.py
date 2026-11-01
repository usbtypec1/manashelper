"""Version one of the editable interface format; no execution or persistence."""

from __future__ import annotations

from string import Formatter
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
DelegateId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$", max_length=120)]
Scalar = StrictStr | StrictBool | StrictInt | StrictFloat | None
LocaleCode = Literal["en", "ru", "ky", "tr", "zh"]
ValueType = Literal["text", "integer", "number", "boolean"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def template_parameters(text: str) -> set[str]:
    """Accept named placeholders only, without attribute access or formatting code."""
    parameters = set()
    for _, name, specification, conversion in Formatter().parse(text):
        if name is None:
            continue
        if not name.isidentifier() or specification or conversion:
            raise ValueError("Only plain named placeholders are supported")
        parameters.add(name)
    return parameters


class CatalogText(ContractModel):
    kind: Literal["catalog"]
    key: Annotated[str, Field(min_length=1, max_length=120)]
    parameters: dict[Identifier, Value] = Field(default_factory=dict)


class InlineText(ContractModel):
    kind: Literal["inline"]
    translations: dict[LocaleCode, Annotated[str, Field(min_length=1, max_length=4096)]]
    themes: dict[Literal["halloween"], dict[LocaleCode, Annotated[str, Field(min_length=1, max_length=4096)]]] = Field(
        default_factory=dict
    )
    parameters: dict[Identifier, Value] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_translations(self) -> InlineText:
        if "en" not in self.translations:
            raise ValueError("An English fallback is required")
        expected = template_parameters(self.translations["en"])
        if expected != set(self.parameters):
            raise ValueError("Each placeholder requires an explicit parameter binding")
        variants = [*self.translations.values(), *(text for theme in self.themes.values() for text in theme.values())]
        if any(template_parameters(text) != expected for text in variants):
            raise ValueError("All translations and themes must use the same placeholders")
        return self


Text = Annotated[CatalogText | InlineText, Field(discriminator="kind")]


class LiteralValue(ContractModel):
    kind: Literal["literal"]
    value: Scalar


class ReferenceValue(ContractModel):
    kind: Literal["ref"]
    scope: Literal["data", "user", "capabilities"]
    field: Identifier


Value = Annotated[LiteralValue | ReferenceValue, Field(discriminator="kind")]


class Compare(ContractModel):
    kind: Literal["compare"]
    left: ReferenceValue
    operator: Literal["eq", "ne", "in", "lt", "le", "gt", "ge"]
    right: Value | list[Scalar]

    @model_validator(mode="after")
    def check_operand(self) -> Compare:
        if (self.operator == "in") != isinstance(self.right, list):
            raise ValueError("Only the 'in' operator accepts a list operand")
        return self


class Exists(ContractModel):
    kind: Literal["exists"]
    reference: ReferenceValue


AtomicCondition = Annotated[Compare | Exists, Field(discriminator="kind")]


class ConditionGroup(ContractModel):
    kind: Literal["all", "any"]
    conditions: Annotated[list[AtomicCondition], Field(min_length=1, max_length=16)]


Predicate = Annotated[Compare | Exists | ConditionGroup, Field(discriminator="kind")]


class TransitionButton(ContractModel):
    kind: Literal["transition"]
    id: Identifier
    label: Text
    target: Identifier
    assignments: dict[Identifier, Value] = Field(default_factory=dict)
    when: Predicate | None = None


class UrlButton(ContractModel):
    kind: Literal["url"]
    id: Identifier
    label: Text
    url: HttpUrl
    when: Predicate | None = None


Button = Annotated[TransitionButton | UrlButton, Field(discriminator="kind")]
ButtonRows = Annotated[list[Annotated[list[Button], Field(min_length=1, max_length=8)]], Field(max_length=20)]


class MenuNode(ContractModel):
    kind: Literal["menu"]
    id: Identifier
    text: Annotated[list[Text], Field(min_length=1, max_length=8)]
    keyboard: Literal["reply", "inline"]
    buttons: ButtonRows


class InputNode(ContractModel):
    kind: Literal["input"]
    id: Identifier
    text: Annotated[list[Text], Field(min_length=1, max_length=8)]
    field: Identifier
    input_type: Literal["text", "integer", "choice"]
    next: Identifier
    error: Text
    buttons: ButtonRows = Field(default_factory=list)
    min_length: Annotated[int, Field(ge=0)] = 1
    max_length: Annotated[int, Field(ge=1, le=4000)] = 4000
    minimum: int | None = None
    maximum: int | None = None
    choices: list[Scalar] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_limits(self) -> InputNode:
        if self.min_length > self.max_length:
            raise ValueError("min_length exceeds max_length")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum exceeds maximum")
        if bool(self.choices) != (self.input_type == "choice"):
            raise ValueError("Only choice inputs require a nonempty choices list")
        if self.input_type != "integer" and (self.minimum is not None or self.maximum is not None):
            raise ValueError("Numeric bounds require an integer input")
        return self


class Branch(ContractModel):
    when: Predicate
    target: Identifier


class ConditionNode(ContractModel):
    kind: Literal["condition"]
    id: Identifier
    branches: Annotated[list[Branch], Field(min_length=1, max_length=16)]
    default: Identifier


class ActionNode(ContractModel):
    kind: Literal["action"]
    id: Identifier
    delegate: DelegateId
    contract_version: Annotated[int, Field(ge=1)] = 1
    arguments: dict[Identifier, Value] = Field(default_factory=dict)
    results: dict[Identifier, Identifier] = Field(default_factory=dict)
    outcomes: Annotated[dict[Identifier, Identifier], Field(min_length=1)]


class EndNode(ContractModel):
    kind: Literal["end"]
    id: Identifier
    status: Literal["completed", "cancelled", "handed_off"]
    text: list[Text] = Field(default_factory=list)
    return_flow: Identifier | None = None
    feature: Identifier | None = None

    @model_validator(mode="after")
    def check_handoff(self) -> EndNode:
        if (self.status == "handed_off") != (self.feature is not None):
            raise ValueError("Only handed_off endings require a feature")
        if self.feature is not None and self.return_flow is not None:
            raise ValueError("A handoff cannot also start another flow")
        return self


Node = Annotated[MenuNode | InputNode | ConditionNode | ActionNode | EndNode, Field(discriminator="kind")]


class DataField(ContractModel):
    type: ValueType
    nullable: bool = False


class Position(ContractModel):
    x: float
    y: float


class FlowDocument(ContractModel):
    schema_version: Literal[1]
    id: Identifier
    entry: Identifier
    navigation_entries: dict[Literal["study"], Identifier] = Field(default_factory=dict)
    fields: dict[Identifier, DataField] = Field(default_factory=dict)
    initial_data: dict[Identifier, Scalar] = Field(default_factory=dict)
    nodes: Annotated[list[Node], Field(min_length=1, max_length=200)]
    layout: dict[Identifier, Position] = Field(default_factory=dict)

    @field_validator("schema_version", mode="before")
    @classmethod
    def check_version_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value
