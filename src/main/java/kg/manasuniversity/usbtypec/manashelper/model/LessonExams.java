package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.List;

public record LessonExams(
        String lessonName,
        String lessonCode,
        List<Exam> exams
) {
}
