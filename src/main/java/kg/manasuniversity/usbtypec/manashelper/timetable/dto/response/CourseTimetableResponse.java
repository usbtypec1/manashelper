package kg.manasuniversity.usbtypec.manashelper.timetable.dto.response;

import kg.manasuniversity.usbtypec.manashelper.timetable.enums.LessonType;

import java.time.LocalTime;
import java.util.List;

public record CourseTimetableResponse(
        int courseId,
        List<Lesson> lessons
) {
  public record Lesson(
          String name,
          String teacherName,
          String location,
          LocalTime startsAt,
          LocalTime endsAt,
          int weekday,
          LessonType type
  ) {
  }
}
