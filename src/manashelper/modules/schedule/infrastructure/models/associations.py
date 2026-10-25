from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Table

from manashelper.db.base import Base

user_courses = Table(
    "user_courses",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True),
)
