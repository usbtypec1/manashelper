package kg.manasuniversity.usbtypec.manashelper.timetable.model;

import kg.manasuniversity.usbtypec.manashelper.timetable.enums.LessonType;

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
