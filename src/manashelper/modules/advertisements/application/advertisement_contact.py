from dataclasses import dataclass

from manashelper.modules.advertisements.domain.contact import ContactStatus


@dataclass(frozen=True, slots=True)
class ContactReveal:
    advertisement_title: str
    contact: ContactStatus
