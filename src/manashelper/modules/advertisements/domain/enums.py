from enum import StrEnum


class AdvertisementStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class AdvertisementMediaType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
