package kg.manasuniversity.usbtypec.manashelper.timetable.model;

import java.util.List;

public record TimetableLessonChanges(
    List<CourseLesson> addedLessons,
    List<CourseLesson> removedLessons
) {
}
