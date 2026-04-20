package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.mapper.LessonMapper;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseTimetable;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.LessonRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class LessonBuilderService {
    private final LessonRepository lessonRepository;
    private final LessonMapper lessonMapper;

    public List<Lesson> getLastSynchronizedLessons(Course course) {
        UUID lastSynchronizationId = lessonRepository
            .findTopByCourseOrderByCreatedAtDesc(course)
            .map(Lesson::getSynchronizationId)
            .orElse(null);

        return lastSynchronizationId != null
            ? lessonRepository.findByCourseAndSynchronizationIdWithCourse(course, lastSynchronizationId)
            : Collections.emptyList();
    }

    public List<Lesson> buildLessons(
        Course course,
        List<CourseTimetable> timetableResponse,
        UUID synchronizationId) {
        return timetableResponse
            .stream()
            .map(lesson -> lessonMapper.mapResponseLessonToEntity(lesson, course, synchronizationId))
            .toList();
    }
}
