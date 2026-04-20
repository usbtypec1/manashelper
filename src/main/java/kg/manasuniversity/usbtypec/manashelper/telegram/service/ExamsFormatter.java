package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import kg.manasuniversity.usbtypec.manashelper.user.model.Exam;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonExams;

import java.util.ArrayList;
import java.util.List;

public class ExamsFormatter {

    public static String format(List<LessonExams> lessonsExams) {
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

    private static String formatNone(String value) {
        return value != null ? value : "-";
    }
}