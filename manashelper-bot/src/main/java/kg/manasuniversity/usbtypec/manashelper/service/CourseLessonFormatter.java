package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.LessonType;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import org.springframework.stereotype.Component;

@Component
public class CourseLessonFormatter {

    public String formatAddedLesson(CourseLesson courseLesson) {
        StringBuilder builder = new StringBuilder();
        builder.append(String.format("✅ <b>Новый урок:</b> %s (%s)\n",
            courseLesson.lessonName(),
            formatLessonType(courseLesson.type())));
        builder.append(String.format("🧑‍🏫 <b>Преподаватель:</b> %s\n",
            courseLesson.teacherName()));
        builder.append(String.format("📍 <b>Место:</b> %s\n",
            courseLesson.location()));
        builder.append(String.format("🗓 %s в %s-%s.",
            formatWeekday(courseLesson.weekday()),
            courseLesson.startsAt(),
            courseLesson.endsAt()));
        return builder.toString();
    }

    public String formatRemovedLesson(CourseLesson courseLesson) {
        StringBuilder builder = new StringBuilder();
        builder.append(String.format("❌ <b>Удален урок:</b> %s (%s)\n",
            courseLesson.lessonName(),
            formatLessonType(courseLesson.type())));
        builder.append(String.format("🧑‍🏫 <b>Преподаватель:</b> %s\n",
            courseLesson.teacherName()));
        builder.append(String.format("📍 <b>Место:</b> %s\n",
            courseLesson.location()));
        builder.append(String.format("🗓 %s в %s-%s.",
            formatWeekday(courseLesson.weekday()),
            courseLesson.startsAt(),
            courseLesson.endsAt()));
        return builder.toString();
    }

    private static String formatWeekday(int weekday) {
        return switch (weekday) {
            case 1 -> "Понедельник";
            case 2 -> "Вторник";
            case 3 -> "Среда";
            case 4 -> "Четверг";
            case 5 -> "Пятница";
            case 6 -> "Суббота";
            case 7 -> "Воскресенье";
            default -> "Неизвестный день";
        };
    }

    private static String formatLessonType(LessonType lessonType) {
        return switch (lessonType) {
            case MANDATORY_MAJOR -> "Обязательный (профильный)";
            case MANDATORY_GENERAL -> "Обязательный (общий)";
            case ELECTIVE_MAJOR -> "Выборочный (профильный)";
            case ELECTIVE_OTHER -> "Выборочный (общий)";
        };
    }
}