from typing import Protocol


class PublicationRemover(Protocol):
    async def delete_publications(self, message_ids: list[int]) -> None: ...
