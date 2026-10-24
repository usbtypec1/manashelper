import uuid
from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class AdvertisementFormAction(StrEnum):
    SKIP_PRICE = "skip_price"
    DONE_MEDIA = "done_media"
    CONFIRM_SUBMIT = "confirm_submit"
    CANCEL = "cancel"


class AdvertisementFormCallback(CallbackData, prefix="ad_form"):
    action: AdvertisementFormAction


class AdvertisementExpiryOption(StrEnum):
    MIN_45 = "min_45"
    HOURS_6 = "hours_6"
    HOURS_24 = "hours_24"
    DAYS_7 = "days_7"
    NONE = "none"


class AdvertisementExpiryCallback(CallbackData, prefix="ad_expiry"):
    option: AdvertisementExpiryOption


class AdvertisementsPageCallback(CallbackData, prefix="ads_page"):
    page: int


class AdvertisementCallback(CallbackData, prefix="ad"):
    id: uuid.UUID
    page: int


class AdvertisementDeleteAction(StrEnum):
    REQUEST = "request"
    CONFIRM = "confirm"
    CANCEL = "cancel"


class AdvertisementDeleteCallback(CallbackData, prefix="ad_delete"):
    id: uuid.UUID
    action: AdvertisementDeleteAction
    page: int


class AdvertisementModerationAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    ADD_COMMENT = "add_comment"
    SKIP_COMMENT = "skip_comment"


class AdvertisementModerationCallback(CallbackData, prefix="ad_moderation"):
    id: uuid.UUID
    action: AdvertisementModerationAction
