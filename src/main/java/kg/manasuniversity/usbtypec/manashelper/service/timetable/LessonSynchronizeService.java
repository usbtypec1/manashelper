package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.model.TimetableLessonChanges;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.LessonRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class LessonSynchronizeService {
  private static final Logger log = LoggerFactory.getLogger(LessonSynchronizeService.class);

  private final CourseRepository courseRepository;
  private final LessonRepository lessonRepository;
  private final TimetableFetchService timetableFetchService;
  private final LessonBuilderService lessonBuilderService;
  private final LessonChangeDetector lessonChangeDetector;
  private final LessonNotificationService lessonNotificationService;

  public LessonSynchronizeService(
          CourseRepository courseRepository,
          LessonRepository lessonRepository,
          TimetableFetchService timetableFetchService,
          LessonBuilderService lessonBuilderService,
          LessonChangeDetector lessonChangeDetector,
          LessonNotificationService lessonNotificationService) {
    this.courseRepository = courseRepository;
    this.lessonRepository = lessonRepository;
    this.timetableFetchService = timetableFetchService;
    this.lessonBuilderService = lessonBuilderService;
    this.lessonChangeDetector = lessonChangeDetector;
    this.lessonNotificationService = lessonNotificationService;
  }

  @Transactional
  public void synchronizeLessons() {
    log.info("Starting lessons synchronization task");
    UUID newSynchronizationId = UUID.randomUUID();

    List<Course> courses = courseRepository.findAllWithDepartment();
    courses.forEach(course -> synchronizeCourse(course, newSynchronizationId));

    log.info("Lessons synchronization task completed");
  }

  private void synchronizeCourse(Course course, UUID newSynchronizationId) {
    log.info("Synchronizing timetable for course ID: {}", course.getId());

    var timetableResponse = timetableFetchService.fetchTimetable(course);
    List<Lesson> storedLessons = lessonBuilderService.getLastSynchronizedLessons(course);
    List<Lesson> newLessons = lessonBuilderService.buildLessons(course, timetableResponse, newSynchronizationId);

    TimetableLessonChanges changes = lessonChangeDetector.detectChanges(storedLessons, newLessons, course);

    if (lessonChangeDetector.hasChanges(changes)) {
      lessonRepository.saveAll(newLessons);
      lessonNotificationService.notifyUsersOfChanges(changes);
    }
  }
}