"""Request-scoped registry of explicitly registered transactional delegates."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ui_flows.application.validation import accepts_scalar
from ui_flows.domain.contracts import Delegate, DelegateContext, DelegateDefinition, DelegateResult
from ui_flows.domain.schema import DataValue
from ui_flows.errors import FlowExecutionError


@dataclass(frozen=True, slots=True)
class DelegateBinding:
    definition: DelegateDefinition
    handler: Delegate


class DelegateRegistry:
    """Handlers may use the current DB transaction; network operations are not supported yet."""

    def __init__(self, bindings: Sequence[DelegateBinding] = ()) -> None:
        self._bindings: dict[tuple[str, int], DelegateBinding] = {}
        for binding in bindings:
            key = (binding.definition.id, binding.definition.version)
            if key in self._bindings or len(set(binding.definition.outcomes)) != len(binding.definition.outcomes):
                raise ValueError("Duplicate delegate contract or outcome")
            self._bindings[key] = DelegateBinding(binding.definition.model_copy(deep=True), binding.handler)

    def definitions(self) -> list[DelegateDefinition]:
        return [binding.definition.model_copy(deep=True) for binding in self._bindings.values()]

    def bindings(self) -> list[DelegateBinding]:
        return [
            DelegateBinding(binding.definition.model_copy(deep=True), binding.handler)
            for binding in self._bindings.values()
        ]

    def definition(self, delegate_id: str, version: int) -> DelegateDefinition:
        binding = self._bindings.get((delegate_id, version))
        if binding is None:
            raise FlowExecutionError("Delegate contract is unavailable")
        return binding.definition.model_copy(deep=True)

    def validate_result(self, delegate_id: str, version: int, result: DelegateResult) -> DelegateResult:
        definition = self.definition(delegate_id, version)
        if result.outcome not in definition.outcomes or not result.values.keys() <= definition.outputs.keys():
            raise FlowExecutionError("Delegate result does not match the contract")
        if any(not accepts_scalar(definition.outputs[name], value) for name, value in result.values.items()):
            raise FlowExecutionError("Delegate result type does not match the contract")
        return DelegateResult(result.outcome, dict(result.values))

    def validate_arguments(self, delegate_id: str, version: int, arguments: Mapping[str, DataValue]) -> None:
        definition = self.definition(delegate_id, version)
        required = {name for name, parameter in definition.inputs.items() if parameter.required}
        if not required <= arguments.keys() or not arguments.keys() <= definition.inputs.keys():
            raise FlowExecutionError("Delegate arguments do not match the contract")
        if any(not accepts_scalar(definition.inputs[name], value) for name, value in arguments.items()):
            raise FlowExecutionError("Delegate argument type does not match the contract")

    async def execute(
        self,
        delegate_id: str,
        version: int,
        context: DelegateContext,
        arguments: Mapping[str, DataValue],
        *,
        external: bool = False,
    ) -> DelegateResult:
        binding = self._bindings.get((delegate_id, version))
        if binding is None:
            raise FlowExecutionError("Delegate contract is unavailable")
        definition = binding.definition
        if (definition.effect == "external") != external:
            raise FlowExecutionError("External delegates require a committed operation claim")
        self.validate_arguments(delegate_id, version, arguments)
        result = await binding.handler(context, dict(arguments))
        return self.validate_result(delegate_id, version, result)


class ExternalDelegateRegistry(DelegateRegistry):
    def __init__(self, bindings: Sequence[DelegateBinding] = ()) -> None:
        if any(binding.definition.effect != "external" for binding in bindings):
            raise ValueError("External handlers cannot own transactional delegates")
        super().__init__(bindings)
