from manashelper.repositories.action_log_repository import ActionLogRepository


class ActionLogService:
    def __init__(self, action_log_repository: ActionLogRepository) -> None:
        self._action_log_repository = action_log_repository

    def log_message(self, chat_id: int, user_id: int, message_text: str | None) -> None:
        self._action_log_repository.add(chat_id, user_id, callback_query_data=None, message_text=message_text)

    def log_callback_query(self, chat_id: int, user_id: int, callback_query_data: str | None) -> None:
        self._action_log_repository.add(chat_id, user_id, callback_query_data=callback_query_data, message_text=None)
