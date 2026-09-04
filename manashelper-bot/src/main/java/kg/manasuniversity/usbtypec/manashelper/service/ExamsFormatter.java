package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.Exam;
import kg.manasuniversity.usbtypec.manashelper.model.LessonExams;
import lombok.experimental.UtilityClass;

import java.util.ArrayList;
import java.util.List;

@UtilityClass
public class ExamsFormatter {

    public String format(List<LessonExams> lessonsExams) {
        List<String> lines = new ArrayList<>();

        for (LessonExams lesson : lessonsExams) {

            List<String> lessonLines = new ArrayList<>();

            lessonLines.add(
                "<b>" + lesson.lessonName()
                    + " (" + lesson.lessonCode() + ")</b>"
            );

            for (Exam exam : lesson.exams()) {

                lessonLines.add(
                    " - " + exam.name()
                        + ": " + formatNone(exam.score())
                );
            }

            lines.add(String.join("\n", lessonLines));
        }

        if (lines.isEmpty()) {
            return "У вас нет оценок за экзамены.";
        }

        return String.join("\n\n", lines);
    }

    private String formatNone(String value) {
        return value != null ? value : "-";
    }
}