package kg.manasuniversity.usbtypec.manashelper.model;

import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;

import java.time.LocalTime;

public record CourseLesson(
    String departmentName,
    int courseId,
    int courseNumber,
    LocalTime startsAt,
    LocalTime endsAt,
    String lessonName,
    String teacherName,
    String location,
    LessonType type,
    int weekday
) {
}
