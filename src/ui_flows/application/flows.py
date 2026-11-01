from ui_flows.application.delegates import DelegateRegistry
from ui_flows.application.policy import FlowPolicy
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.schema import EndNode, FlowDocument
from ui_flows.domain.state import Draft, PublishedFlow
from ui_flows.errors import FlowConflictError, FlowNotFoundError, InvalidFlowError
from ui_flows.ports.repositories import FlowStore


class FlowService:
    def __init__(self, repository: FlowStore, registry: DelegateRegistry, policy: FlowPolicy) -> None:
        self._repository = repository
        self._registry = registry
        self._policy = policy

    async def create(self, document: FlowDocument) -> Draft:
        return await self._repository.create(document)

    async def get(self, flow_id: str) -> Draft:
        return await self._repository.get(flow_id)

    async def version(self, flow_id: str, version: int) -> PublishedFlow:
        return await self._repository.version(flow_id, version)

    async def save(self, document: FlowDocument, expected_revision: int) -> Draft:
        return await self._repository.save_draft(document, expected_revision)

    async def validate(self, document: FlowDocument) -> None:
        self._policy.validate(document, self._registry)
        issues = []
        for index, node in enumerate(document.nodes):
            if isinstance(node, EndNode) and node.return_flow is not None and node.return_flow != document.id:
                try:
                    target = await self._repository.published(node.return_flow)
                except FlowNotFoundError:
                    issues.append(
                        ContractIssue(
                            code="unpublished_return_flow",
                            path=f"/nodes/{index}/return_flow",
                            message="Return scenario must have a published version",
                            node_id=node.id,
                        )
                    )
                else:
                    entry = next(item for item in target.document.nodes if item.id == target.document.entry)
                    if entry.kind not in {"menu", "input"}:
                        issues.append(
                            ContractIssue(
                                code="invalid_return_entry",
                                path=f"/nodes/{index}/return_flow",
                                message="Return scenario must start at an interactive screen",
                                node_id=node.id,
                            )
                        )
            elif isinstance(node, EndNode) and node.return_flow == document.id:
                entry = next(item for item in document.nodes if item.id == document.entry)
                if entry.kind not in {"menu", "input"}:
                    issues.append(
                        ContractIssue(
                            code="invalid_return_entry",
                            path=f"/nodes/{index}/return_flow",
                            message="Return scenario must start at an interactive screen",
                            node_id=node.id,
                        )
                    )
        if issues:
            raise InvalidFlowError(issues)

    async def publish(self, flow_id: str, expected_revision: int, author_id: int) -> PublishedFlow:
        async with self._repository.atomic():
            draft = await self._repository.get(flow_id, lock=True)
            if draft.revision != expected_revision:
                raise FlowConflictError("The draft revision has changed")
            previous = await self._repository.find_revision(flow_id, expected_revision)
            if previous is not None:
                return previous  # A retry must not reactivate an old publication after rollback.
            await self.validate(draft.document)
            return await self._repository.add_version(draft, author_id)

    async def activate(self, flow_id: str, version: int, expected_published_version: int | None) -> Draft:
        async with self._repository.atomic():
            draft = await self._repository.get(flow_id, lock=True)
            if draft.published_version != expected_published_version:
                raise FlowConflictError("The publication pointer has changed")
            target = await self._repository.version(flow_id, version)
            await self.validate(target.document)
            await self._repository.activate(flow_id, version)
            return await self._repository.get(flow_id)
