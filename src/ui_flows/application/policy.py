from collections.abc import Mapping
from dataclasses import dataclass, field

from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.validation import accepts_scalar, validate_flow
from ui_flows.domain.schema import DataField, FlowDocument, Scalar
from ui_flows.errors import InvalidFlowError


@dataclass(frozen=True, slots=True)
class FlowPolicy:
    catalog_keys: frozenset[str] = frozenset()
    features: frozenset[str] = frozenset()
    capability_fields: Mapping[str, DataField] = field(default_factory=dict)
    capabilities: Mapping[str, Scalar] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.capabilities.keys() != self.capability_fields.keys() or any(
            not accepts_scalar(self.capability_fields[name], value) for name, value in self.capabilities.items()
        ):
            raise ValueError("Capability values do not match their declarations")

    def validate(self, document: FlowDocument, registry: DelegateRegistry) -> None:
        issues = validate_flow(
            document,
            delegates=registry.definitions(),
            features=self.features,
            catalog_keys=self.catalog_keys,
            capabilities=self.capability_fields,
        )
        if issues:
            raise InvalidFlowError(issues)
