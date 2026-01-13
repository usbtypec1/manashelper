package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.List;

public record TimetableLessonChanges(
        List<Lesson> addedLessons,
        List<Lesson> removedLessons
) {
}
