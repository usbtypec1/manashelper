from manashelper.modules.obis.application.models import AttendanceRecord, ExamModel, LessonExamsModel, Transcript
from manashelper.modules.obis.infrastructure.client import ObisClient
from manashelper.modules.obis.infrastructure.parser import parse_attendance_page, parse_exam_grades_page
from manashelper.modules.obis.infrastructure.transcript_parser import parse_transcript


class ObisResultsSource:
    async def fetch_transcript(self, student_number: str, password: str) -> Transcript:
        return parse_transcript(await self._client.fetch_transcript_html(student_number, password))

    def __init__(self, client: ObisClient) -> None:
        self._client = client

    async def fetch_exam_grades(self, student_number: str, password: str) -> list[LessonExamsModel]:
        html = await self._client.fetch_exam_grades_html(student_number, password)
        return [
            LessonExamsModel(
                lesson.lesson_name,
                lesson.lesson_code,
                [ExamModel(exam.name, exam.score) for exam in lesson.exams],
            )
            for lesson in parse_exam_grades_page(html)
        ]

    async def fetch_attendance(self, student_number: str, password: str) -> list[AttendanceRecord]:
        html = await self._client.fetch_attendance_html(student_number, password)
        return [
            AttendanceRecord(
                lesson.lesson_name,
                lesson.lesson_code,
                lesson.theory_skips_percentage,
                lesson.practice_skips_percentage,
            )
            for lesson in parse_attendance_page(html)
        ]
