package kg.manasuniversity.usbtypec.manashelper.timetable.dto.response;

import kg.manasuniversity.usbtypec.manashelper.timetable.enums.LessonType;

import java.time.LocalTime;

public record CourseTimetableResponse(
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
