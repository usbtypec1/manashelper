package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.model.PeriodTimetable;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.LessonRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class LessonBuilderService {
  private final LessonRepository lessonRepository;

  public LessonBuilderService(LessonRepository lessonRepository) {
    this.lessonRepository = lessonRepository;
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
    return timetableResponse.timetable().stream()
            .flatMap(periodTimetable -> buildLessonsForPeriod(course, periodTimetable, synchronizationId).stream())
            .collect(Collectors.toList());
  }

  private List<Lesson> buildLessonsForPeriod(
          Course course,
          PeriodTimetable periodTimetable,
          UUID synchronizationId) {
    TimeRange timeRange = TimeRangeParser.parse(periodTimetable.period());
    List<Lesson> lessons = new ArrayList<>();

    lessons.addAll(createLessonsForDay(periodTimetable.monday(), course, timeRange, 1, synchronizationId));
    lessons.addAll(createLessonsForDay(periodTimetable.tuesday(), course, timeRange, 2, synchronizationId));
    lessons.addAll(createLessonsForDay(periodTimetable.wednesday(), course, timeRange, 3, synchronizationId));
    lessons.addAll(createLessonsForDay(periodTimetable.thursday(), course, timeRange, 4, synchronizationId));
    lessons.addAll(createLessonsForDay(periodTimetable.friday(), course, timeRange, 5, synchronizationId));

    return lessons;
  }

  private List<Lesson> createLessonsForDay(
          List<kg.manasuniversity.usbtypec.manashelper.model.Lesson> dayLessons,
          Course course,
          TimeRange timeRange,
          int weekday,
          UUID synchronizationId) {
    return dayLessons.stream()
            .map(lesson -> createLesson(lesson, course, timeRange, weekday, synchronizationId))
            .collect(Collectors.toList());
  }

  private Lesson createLesson(
          kg.manasuniversity.usbtypec.manashelper.model.Lesson lessonData,
          Course course,
          TimeRange timeRange,
          int weekday,
          UUID synchronizationId) {
    return new Lesson(
            synchronizationId,
            lessonData.name(),
            course,
            lessonData.teacherName(),
            lessonData.location(),
            timeRange.startsAt(),
            timeRange.endsAt(),
            weekday,
            lessonData.type()
    );
  }
}
