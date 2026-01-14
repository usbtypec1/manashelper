package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.mapper.LessonMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.LessonRepository;
import org.springframework.stereotype.Service;

import java.util.Collections;
import java.util.List;
import java.util.UUID;

@Service
public class LessonBuilderService {
  private final LessonRepository lessonRepository;
  private final LessonMapper lessonMapper;

  public LessonBuilderService(LessonRepository lessonRepository, LessonMapper lessonMapper) {
    this.lessonRepository = lessonRepository;
    this.lessonMapper = lessonMapper;
  }

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
          CourseTimetableResponse timetableResponse,
          UUID synchronizationId) {
    return timetableResponse
            .lessons()
            .stream()
            .map(lesson -> lessonMapper.mapResponseLessonToEntity(lesson, course, synchronizationId))
            .toList();
  }
}
