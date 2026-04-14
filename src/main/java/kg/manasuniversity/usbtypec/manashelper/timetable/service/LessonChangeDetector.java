package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.mapper.LessonMapper;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.TimetableLessonChanges;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class LessonChangeDetector {
    private static final String SIGNATURE_DELIMITER = "|";

    private final LessonMapper lessonMapper;

    public TimetableLessonChanges detectChanges(
        List<Lesson> storedLessons,
        List<Lesson> newLessons,
        Course course) {
        Set<String> storedSignatures = createSignatureSet(storedLessons);
        Set<String> newSignatures = createSignatureSet(newLessons);

        List<CourseLesson> addedLessons = findLessonsNotInSet(newLessons, storedSignatures, course);
        List<CourseLesson> removedLessons = findLessonsNotInSet(storedLessons, newSignatures, course);

        return new TimetableLessonChanges(addedLessons, removedLessons);
    }

    public boolean hasChanges(TimetableLessonChanges changes) {
        return !changes.addedLessons().isEmpty() || !changes.removedLessons().isEmpty();
    }

    private Set<String> createSignatureSet(List<Lesson> lessons) {
        return lessons.stream()
            .map(this::createLessonSignature)
            .collect(Collectors.toSet());
    }

    private List<CourseLesson> findLessonsNotInSet(
        List<Lesson> lessons,
        Set<String> signatures,
        Course course) {
        return lessons.stream()
            .filter(lesson -> !signatures.contains(createLessonSignature(lesson)))
            .map(lesson -> lessonMapper.mapEntityAndCourseToCourseLesson(lesson, course))
            .collect(Collectors.toList());
    }

    private String createLessonSignature(Lesson lesson) {
        return String.join(SIGNATURE_DELIMITER,
            String.valueOf(lesson.getName()),
            String.valueOf(lesson.getTeacherName()),
            String.valueOf(lesson.getLocation()),
            String.valueOf(lesson.getType()),
            String.valueOf(lesson.getStartsAt()),
            String.valueOf(lesson.getEndsAt()),
            String.valueOf(lesson.getWeekday())
        );
    }
}
