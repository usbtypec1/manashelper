from manashelper.platform.i18n.repository import CatalogDraft, CatalogRelease, TextCatalogRepository
from ui_flows.application.texts import validate_text_document
from ui_flows.domain.contracts import ContractIssue
from ui_flows.domain.texts import TextEntry, TextSnapshot
from ui_flows.errors import FlowConflictError, FlowNotFoundError, InvalidFlowError


class TextCatalogService:
    def __init__(self, repository: TextCatalogRepository) -> None:
        self._repository = repository
        self._current: TextSnapshot | None = None
        self._versions: dict[int, TextSnapshot] = {}

    async def current(self) -> TextSnapshot:
        if self._current is None:
            self._current = await self._repository.current()
            self._versions[self._current.release_id] = self._current
        return self._current

    async def version(self, release_id: int) -> TextSnapshot:
        if release_id not in self._versions:
            self._versions[release_id] = await self._repository.version(release_id)
        return self._versions[release_id]

    async def draft(self) -> CatalogDraft:
        return await self._repository.draft()

    async def save_entry(self, key: str, entry: TextEntry, expected_revision: int) -> CatalogDraft:
        draft = await self.draft()
        if draft.revision != expected_revision:
            raise FlowConflictError("Text catalog revision has changed")
        original = next((item for item in draft.document.entries if item.key == key), None)
        if original is None:
            raise FlowNotFoundError("Text key does not exist")
        if any(
            getattr(original, field) != getattr(entry, field)
            for field in ("key", "owner", "parameters", "content_type", "plural_key")
        ):
            raise FlowConflictError("Text key and parameter contracts are immutable")
        document = draft.document.model_copy(
            update={"entries": tuple(entry if item.key == key else item for item in draft.document.entries)}
        )
        issues = validate_text_document(document)
        if issues:
            raise InvalidFlowError(issues)
        return await self._repository.save(document, expected_revision)

    async def publish(self, expected_revision: int, author_id: int) -> CatalogRelease:
        from manashelper.modules.ui_flows.presentation.rendering import FlowRenderer, InvalidScreenError
        from manashelper.platform.i18n.catalog import i18n
        from manashelper.platform.i18n.seed import REPLY_KEYS

        draft = await self.draft()
        if draft.revision != expected_revision:
            raise FlowConflictError("Text catalog revision has changed")
        snapshot = TextSnapshot(0, draft.document)
        previous = await self._repository.published_revision(expected_revision)
        if previous is not None:
            return previous
        labels: dict[tuple[str, str], str] = {}
        reply_keys = REPLY_KEYS | await self._repository.trigger_reply_keys()
        for (key, locale), values in (await self.historical_labels()).items():
            if key in reply_keys:
                for value in values:
                    labels[(locale, value)] = key
        issues = []
        for entry in draft.document.entries:
            if entry.key not in reply_keys:
                continue
            for variant in entry.variants:
                if variant.text.startswith("/"):
                    issues.append(
                        ContractIssue(
                            code="invalid_reply_label",
                            path="/entries/" + entry.key,
                            message="Reply labels must not be parsed as commands",
                        )
                    )
                identity = (variant.locale, variant.text)
                if labels.setdefault(identity, entry.key) != entry.key:
                    issues.append(
                        ContractIssue(
                            code="ambiguous_legacy_label",
                            path="/entries/" + entry.key,
                            message="Reply labels must not conflict with another current or historical action",
                        )
                    )
        if issues:
            raise InvalidFlowError(issues)
        with i18n.use_catalog(snapshot):
            for document in await self._repository.published_flows():
                try:
                    FlowRenderer().validate_document(document, {"eders_enabled": True})
                except InvalidScreenError as error:
                    raise InvalidFlowError(
                        [
                            ContractIssue(
                                code="invalid_catalog_screen",
                                path=error.path,
                                node_id=error.node_id,
                                message="Text release makes a published screen invalid",
                            )
                        ]
                    ) from error
        return await self._repository.publish(expected_revision, author_id)

    async def activate(self, release_id: int, expected_current_release: int) -> CatalogDraft:
        return await self._repository.activate(release_id, expected_current_release)

    async def versions(self) -> list[CatalogRelease]:
        return await self._repository.versions()

    async def historical_labels(self) -> dict[tuple[str, str], frozenset[str]]:
        return await self._repository.historical_labels()
