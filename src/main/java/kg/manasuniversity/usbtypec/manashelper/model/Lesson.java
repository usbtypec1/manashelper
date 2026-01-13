package kg.manasuniversity.usbtypec.manashelper.model;

import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;

public record Lesson(
        int courseId,
        String name,
        String teacherName,
        String location,
        LessonType type,
        int weekday
) {
}
