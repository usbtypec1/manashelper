from aiogram.fsm.state import State, StatesGroup


class FeedbackForm(StatesGroup):
    message = State()
