package kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model;

import java.util.List;

public record LessonExams(
        String lessonName,
        String lessonCode,
        List<Exam> exams
) {
}
