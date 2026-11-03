from manashelper.modules.ui_flows.infrastructure.triggers import TriggerRepository
from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, InvalidScreenError
from manashelper.modules.ui_flows.triggers import trigger_document
from manashelper.platform.i18n.catalog import i18n
from manashelper.platform.i18n.service import TextCatalogService
from ui_flows.application.flows import FlowService
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.ingress import (
    LegacyTarget,
    ScenarioPin,
    TriggerDocument,
    TriggerDraft,
    TriggerManifest,
    TriggerRelease,
)
from ui_flows.domain.schema import EndNode, InputNode, MenuNode
from ui_flows.errors import FlowConflictError, FlowNotFoundError, InvalidFlowError


class TriggerService:
    def __init__(self, repository: TriggerRepository, flows: FlowService, texts: TextCatalogService) -> None:
        self._repository, self._flows, self._texts = repository, flows, texts

    async def initialize(self, author_id: int, document: TriggerDocument | None = None) -> None:
        await self._repository.initialize(document)
        draft = await self.draft()
        if draft.current_release is None:
            ready = True
            for flow_id in {
                binding.target.flow_id for binding in draft.document.bindings if binding.target.kind == "scenario"
            }:
                try:
                    ready &= (await self._flows.get(flow_id)).published_version is not None
                except FlowNotFoundError:
                    ready = False
            if ready:
                await self.publish(draft.revision, author_id)
            else:
                # An authored, unpublished built-in must not prevent startup or be overwritten.
                # Keep the runtime draft; the first compatibility manifest uses its legacy owners.
                bindings = [
                    binding.model_copy(
                        update={"target": LegacyTarget(adapter=binding.fallback_adapter), "fallback_adapter": None}
                    )
                    if binding.target.kind == "scenario" and binding.fallback_adapter
                    else binding
                    for binding in draft.document.bindings
                    if binding.target.kind == "legacy" or binding.fallback_adapter is not None
                ]
                manifest = TriggerManifest(
                    document=TriggerDocument(bindings=bindings),
                    scenarios=[],
                    text_catalog_release=(await self._texts.current()).release_id,
                )
                await self._repository.publish(manifest, draft.revision, author_id)

    async def current(self) -> TriggerRelease:
        return await self._repository.current()

    async def draft(self) -> TriggerDraft:
        return await self._repository.draft()

    async def validate(self, document: TriggerDocument) -> None:
        from manashelper.modules.ui_flows.presentation.ingress_codecs import CODECS

        baseline = {item.id: item for item in trigger_document().bindings}
        issues: list[ContractIssue] = []

        def issue(index: int, code: str) -> None:
            issues.append(ContractIssue(code=code, path=f"/bindings/{index}", message="Invalid trigger: " + code))

        snapshot = await self._texts.current()
        history = await self._texts.historical_labels()
        identities = set()
        for index, binding in enumerate(document.bindings):
            matcher = binding.matcher
            if matcher.action is not None and matcher.kind != "callback":
                issue(index, "action_requires_callback")
            if matcher.arguments != "none" and matcher.kind not in {"command", "prefix"}:
                issue(index, "unsupported_argument_matcher")
            if binding.id in identities:
                issue(index, "duplicate_binding_id")
            identities.add(binding.id)
            if set(binding.capabilities) - {"eders_enabled"}:
                issue(index, "unknown_capability")
            if matcher.kind == "command" and (
                not matcher.key.isascii()
                or not matcher.key.replace("_", "").isalnum()
                or not matcher.key[0].islower()
                or len(matcher.key) > 32
            ):
                issue(index, "invalid_command")
            if matcher.kind in {"prefix", "deep_link"} and (
                len(matcher.key) > 64 or any(c.isspace() for c in matcher.key)
            ):
                issue(index, "invalid_payload")
            if matcher.kind == "prefix" and matcher.arguments != "uuid":
                issue(index, "typed_suffix_required")
            if matcher.kind == "callback" and matcher.key not in CODECS:
                issue(index, "unknown_callback_codec")
            if matcher.kind == "reply_label" and (
                matcher.key not in snapshot.keys
                or snapshot.entry(matcher.key).content_type != "label"
                or snapshot.entry(matcher.key).parameters
            ):
                issue(index, "unknown_label")
            if (
                matcher.kind == "command"
                and matcher.key in {"broadcast", "editor", "flow_demo"}
                and binding.access != "admin"
            ):
                issue(index, "reserved_admin_entry")
            original = baseline.get(binding.id)
            compatibility = (
                original.model_copy(
                    update={"target": LegacyTarget(adapter=original.fallback_adapter), "fallback_adapter": None}
                )
                if original and original.fallback_adapter
                else None
            )
            if binding.target.kind == "legacy" and binding not in (original, compatibility):
                issue(index, "immutable_legacy_adapter")
            if binding.fallback_adapter is not None and (
                original is None
                or binding.fallback_adapter
                != (original.target.adapter if original.target.kind == "legacy" else original.fallback_adapter)
                or binding.matcher != original.matcher
            ):
                issue(index, "invalid_legacy_fallback")
            if binding.target.kind == "scenario" and (binding.scope != "private" or binding.policy == "preserve"):
                issue(index, "unsupported_scenario_policy")
            owned_preference_callback = (
                matcher.kind == "callback"
                and matcher.key == "settings"
                and matcher.action
                in {
                    "open_language",
                    "open_theme",
                    "back_to_settings",
                }
            )
            if (
                binding.target.kind == "scenario"
                and matcher.kind in {"callback", "native_reply"}
                and not owned_preference_callback
            ):
                issue(index, "callback_requires_owned_action_adapter")
            if binding.policy == "call" and (
                binding.target.kind != "scenario"
                or binding.target.entry is not None
                or binding.target.navigation is not None
            ):
                issue(index, "invalid_call_target")
            for previous in document.bindings[:index]:
                a, b = previous.matcher, matcher
                if previous.scope != binding.scope and "any" not in {previous.scope, binding.scope}:
                    continue
                overlap = a.kind == b.kind and a.key == b.key and (a.action == b.action or None in {a.action, b.action})
                if a.kind in {"deep_link", "prefix"} and b.kind in {"deep_link", "prefix"}:
                    overlap |= (a.kind == "prefix" and b.key.startswith(a.key)) or (
                        b.kind == "prefix" and a.key.startswith(b.key)
                    )
                if a.kind == b.kind == "native_reply":
                    overlap = True
                if a.kind == b.kind == "reply_label" and a.key in snapshot.keys and b.key in snapshot.keys:
                    for locale in ("en", "ru", "ky", "tr", "zh"):
                        first = set(history.get((a.key, locale), ())) | {
                            snapshot.gettext(a.key, locale, theme) for theme in ("basic", "halloween")
                        }
                        second = set(history.get((b.key, locale), ())) | {
                            snapshot.gettext(b.key, locale, theme) for theme in ("basic", "halloween")
                        }
                        overlap |= bool(first & second)
                if overlap:
                    issue(index, "ambiguous_binding")
        if issues:
            raise InvalidFlowError(issues)

    async def save(self, document: TriggerDocument, expected_revision: int) -> TriggerDraft:
        return await self._repository.save(document, expected_revision)

    async def _manifest(self, document: TriggerDocument) -> TriggerManifest:
        await self.validate(document)
        pins: dict[str, ScenarioPin] = {}
        pending = [binding.target.flow_id for binding in document.bindings if binding.target.kind == "scenario"]
        while pending:
            flow_id = pending.pop()
            if flow_id in pins:
                continue
            draft = await self._flows.get(flow_id)
            if draft.published_version is None:
                raise InvalidFlowError(
                    [
                        ContractIssue(
                            code="unpublished_trigger_target",
                            path="/bindings",
                            message="Publish the target scenario first",
                        )
                    ]
                )
            version = await self._flows.version(flow_id, draft.published_version)
            await self._flows.validate(version.document, dependencies=version.dependencies)
            snapshot = await self._texts.version(version.text_catalog_release or 1)
            with i18n.use_catalog(snapshot):
                try:
                    FlowRenderer().validate_document(version.document, {"eders_enabled": True})
                except InvalidScreenError as error:
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="invalid_trigger_screen",
                                path=error.path,
                                message="Trigger target cannot render safely",
                            )
                        ]
                    ) from error
            for binding in document.bindings:
                if (
                    binding.target.kind == "scenario"
                    and binding.target.flow_id == flow_id
                    and binding.target.entry is not None
                ) and not any(node.id == binding.target.entry for node in version.document.nodes):
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="unknown_trigger_entry",
                                path="/bindings",
                                message="Trigger entry must exist in its pinned scenario",
                            )
                        ]
                    )
            pins[flow_id] = ScenarioPin(
                flow_id=flow_id, version=version.version, text_catalog_release=snapshot.release_id
            )
            for binding in document.bindings:
                if binding.target.kind != "scenario" or binding.target.flow_id != flow_id:
                    continue
                if binding.policy == "call" and (
                    version.document.outputs
                    or not isinstance(
                        next(node for node in version.document.nodes if node.id == version.document.entry),
                        (MenuNode, InputNode),
                    )
                ):
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="invalid_call_contract",
                                path="/bindings",
                                message="A call entry must start at a wait and export no parent data",
                            )
                        ]
                    )
                if not version.document.inputs.keys() <= (
                    binding.target.arguments.keys() | version.document.initial_data.keys()
                ):
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="missing_trigger_inputs",
                                path="/bindings",
                                message="Bind every required scenario input before publishing",
                            )
                        ]
                    )
                for field, source in binding.target.arguments.items():
                    declaration = version.document.fields.get(field)
                    expected_type = "text" if source == "argument" else "integer"
                    if (
                        declaration is None
                        or declaration.type != expected_type
                        or (source == "argument" and binding.matcher.arguments == "none")
                    ):
                        raise InvalidFlowError(
                            [
                                ContractIssue(
                                    code="invalid_trigger_arguments",
                                    path="/bindings",
                                    message="Bind checked arguments to declared fields of the same type",
                                )
                            ]
                        )
                if binding.matcher.arguments != "none" and "argument" not in binding.target.arguments.values():
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="unbound_trigger_argument",
                                path="/bindings",
                                message="Scenario launch arguments require an explicit field binding",
                            )
                        ]
                    )
            pending.extend(
                node.return_flow
                for node in version.document.nodes
                if isinstance(node, EndNode) and node.return_flow is not None
            )
        return TriggerManifest(
            document=document,
            scenarios=sorted(pins.values(), key=lambda pin: pin.flow_id),
            text_catalog_release=(await self._texts.current()).release_id,
        )

    async def publish(self, expected_revision: int, author_id: int) -> TriggerRelease:
        draft = await self.draft()
        if draft.revision != expected_revision:
            raise FlowConflictError("Trigger draft revision has changed")
        previous = await self._repository.published_revision(expected_revision)
        if previous is not None:
            return previous
        manifest = await self._manifest(draft.document)
        return await self._repository.publish(manifest, expected_revision, author_id)

    async def activate(self, release_id: int, expected_current_release: int) -> TriggerDraft:
        # References are immutable and retention never removes versions/releases used by a manifest.
        release = await self._repository.version(release_id)
        await self.validate(release.manifest.document)
        for pin in release.manifest.scenarios:
            version = await self._flows.version(pin.flow_id, pin.version)
            await self._flows.validate(version.document, dependencies=version.dependencies)
        return await self._repository.activate(release_id, expected_current_release)

    async def versions(self) -> list[TriggerRelease]:
        return await self._repository.versions()
