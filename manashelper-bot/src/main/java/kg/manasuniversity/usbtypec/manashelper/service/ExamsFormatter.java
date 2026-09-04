package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.Exam;
import kg.manasuniversity.usbtypec.manashelper.model.LessonExams;
import lombok.experimental.UtilityClass;

import java.util.ArrayList;
import java.util.List;

@UtilityClass
public class ExamsFormatter {

    public String format(List<LessonExams> lessonsExams) {
        if (lessonsExams == null || lessonsExams.isEmpty()) {
            return "У вас нет оценок за экзамены.";
        }
        List<String> lines = lessonsExams.stream().map(ExamsFormatter::formatLessonExams).toList();
        return String.join("\n\n", lines);
    }

    private String formatLessonExams(LessonExams lessonExams) {
        List<String> lessonLines = new ArrayList<>();

        String line = "<b>%s (%s)</b>".formatted(lessonExams.lessonName(), lessonExams.lessonCode());
        lessonLines.add(line);

        lessonExams.exams().stream()
            .map(ExamsFormatter::formatExam)
            .forEach(lessonLines::add);

        return String.join("\n", lessonLines);
    }

    private String formatExam(Exam exam) {
        return "- %s: %s".formatted(exam.name(), formatNone(exam.score()));
    }

    private String formatNone(String value) {
        return value != null ? value : "-";
    }
}