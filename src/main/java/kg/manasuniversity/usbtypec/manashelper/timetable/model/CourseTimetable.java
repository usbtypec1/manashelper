package kg.manasuniversity.usbtypec.manashelper.timetable.model;

import java.time.LocalTime;

public record CourseTimetable(
        int courseId,
        String name,
        String teacherName,
        String location,
        LocalTime startsAt,
        LocalTime endsAt,
        int weekday,
        LessonType type
) {
}
