"""One deterministic resolver; Telegram codecs and legacy handler execution stay in adapters."""

from uuid import UUID

from ui_flows.domain.ingress import IncomingEvent, IngressContext, RouteDecision, TriggerBinding, TriggerRelease
from ui_flows.domain.schema import Scalar
from ui_flows.domain.state import DialogState


def idle_menu(state: DialogState, flow_id: str) -> bool:
    return not state.frames and state.flow_id == flow_id and state.status == "waiting_button" and not state.data


def launch_arguments(binding: TriggerBinding, event: IncomingEvent) -> dict[str, Scalar]:
    if binding.target.kind != "scenario":
        return {}
    argument = event.key[len(binding.matcher.key) :] if binding.matcher.kind == "prefix" else event.arguments
    if binding.matcher.arguments == "uuid":
        argument = str(UUID(argument))
    sources: dict[str, Scalar] = {"argument": argument, "actor_id": event.actor_id, "chat_id": event.chat_id}
    return {field: sources[source] for field, source in binding.target.arguments.items()}


def matches(binding: TriggerBinding, event: IncomingEvent, context: IngressContext) -> bool:
    matcher = binding.matcher
    if matcher.kind == "reply_label":
        return event.kind == "text" and event.text in context.labels.get(matcher.key, ())
    if matcher.kind == "native_reply":
        return event.kind == "reply"
    if matcher.kind == "callback":
        return (
            event.kind == "callback"
            and event.codec == matcher.key
            and (matcher.action is None or matcher.action == event.action)
        )
    if matcher.kind == "prefix":
        return event.kind == "deep_link" and event.key.startswith(matcher.key)
    return event.kind == matcher.kind and event.key == matcher.key


def valid_arguments(binding: TriggerBinding, event: IncomingEvent) -> bool:
    argument = event.key[len(binding.matcher.key) :] if binding.matcher.kind == "prefix" else event.arguments
    match binding.matcher.arguments:
        case "none":
            return not argument
        case "text":
            return len(argument) <= 4096
        case "flow_id":
            return not argument or (
                len(argument) <= 32
                and argument.isascii()
                and argument.replace("_", "").isalnum()
                and argument[0].islower()
            )
        case "uuid":
            try:
                UUID(argument)
                return True
            except ValueError:
                return False


def in_scope(binding: TriggerBinding, event: IncomingEvent) -> bool:
    private = event.chat_type == "private" and event.actor_id == event.chat_id and event.actor_id > 0
    return (
        binding.scope == "any"
        or (binding.scope == "private" and private)
        or (binding.scope == "group" and event.chat_type in {"group", "supergroup"})
    )


def has_access(binding: TriggerBinding, event: IncomingEvent, context: IngressContext) -> bool:
    private = event.chat_type == "private" and event.actor_id == event.chat_id and event.actor_id > 0
    return (
        event.valid
        and event.actor_id > 0
        and in_scope(binding, event)
        and (binding.access != "admin" or (private and event.actor_id == context.admin_id))
        and (binding.access != "moderation" or event.chat_id == context.moderation_chat_id)
        and (set(binding.capabilities) <= context.capabilities)
    )


def authorized(binding: TriggerBinding, event: IncomingEvent, context: IngressContext) -> bool:
    return has_access(binding, event, context) and valid_arguments(binding, event)


def resolve(event: IncomingEvent, release: TriggerRelease, context: IngressContext) -> RouteDecision:
    def decision(kind: str, **values: object) -> RouteDecision:
        return RouteDecision.model_validate({"kind": kind, "release_id": release.id, **values})

    private = event.chat_type == "private" and event.actor_id == event.chat_id and event.actor_id > 0
    if event.actor_id <= 0 or event.update_id < 0 or not event.valid:
        return decision("reject" if event.kind != "unsupported" else "ignore")
    # Structured inputs never become text answers. A displayed reply action precedes global labels.
    if event.kind == "callback" and event.codec == "uf":
        return decision("runtime_callback" if private else "reject")
    if private and context.runtime_flow and event.kind == "text" and context.saved_reply:
        return decision("runtime_text")
    candidates = [
        item for item in release.manifest.document.bindings if matches(item, event, context) and in_scope(item, event)
    ]
    if candidates:
        binding = candidates[0]  # Publication rejects every overlapping matcher.
        if not authorized(binding, event, context):
            return decision("reject")
        owner = binding.target.adapter if binding.target.kind == "legacy" else None
        busy = (context.runtime_flow is not None and context.runtime_busy) or context.legacy_owner is not None
        same = (
            (binding.target.kind == "scenario" and binding.target.flow_id == context.runtime_flow)
            or (owner is not None and owner == context.legacy_owner)
            or (binding.fallback_adapter is not None and binding.fallback_adapter == context.legacy_owner)
        )
        same |= (
            binding.policy == "resume"
            and owner is not None
            and context.runtime_flow is not None
            and context.legacy_owner is None
        )
        if busy and binding.policy not in {"preserve", "replace", "call"} and not same:
            return decision("reject")
        if binding.target.kind == "legacy":
            return decision("legacy", binding_id=binding.id, adapter=owner, policy=binding.policy)
        if binding.policy == "call" and context.legacy_owner is not None and binding.fallback_adapter:
            # Unmigrated in-memory forms retain their existing preference adapter and owner.
            return decision("legacy", binding_id=binding.id, adapter=binding.fallback_adapter, policy="preserve")
        # A survey already owned by the legacy FSM must finish on that owner.
        if binding.fallback_adapter is not None and context.legacy_owner == binding.fallback_adapter:
            return decision("legacy", binding_id=binding.id, adapter=binding.fallback_adapter, policy=binding.policy)
        if (
            not context.rollout
            and not (binding.policy == "resume" and same)
            and not (binding.policy == "call" and context.runtime_flow is not None)
        ):
            return (
                decision("legacy", binding_id=binding.id, adapter=binding.fallback_adapter, policy=binding.policy)
                if binding.fallback_adapter
                else decision("reject")
            )
        pin = next(item for item in release.manifest.scenarios if item.flow_id == binding.target.flow_id)
        return decision(
            "launch",
            binding_id=binding.id,
            flow_id=pin.flow_id,
            flow_version=pin.version,
            entry=binding.target.entry,
            navigation=binding.target.navigation,
            policy=binding.policy,
        )
    if private and context.runtime_flow:
        typed = (event.kind == "contact" and context.runtime_input == "contact") or (
            event.kind == "media" and context.runtime_input == "media"
        )
        return decision("runtime_text" if event.kind == "text" or typed else "reject")
    if context.legacy_owner and event.kind in {"text", "contact", "media", "reply"}:
        return decision("legacy", adapter=context.legacy_owner, policy="preserve")
    # Unknown commands, payloads and callbacks cannot enter a waiting form or fall through to /start.
    return decision("reject" if event.kind in {"command", "deep_link", "callback"} else "ignore")
