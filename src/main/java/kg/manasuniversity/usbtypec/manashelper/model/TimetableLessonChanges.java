package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.List;

public record TimetableLessonChanges(
        List<CourseLesson> addedLessons,
        List<CourseLesson> removedLessons
) {
}
