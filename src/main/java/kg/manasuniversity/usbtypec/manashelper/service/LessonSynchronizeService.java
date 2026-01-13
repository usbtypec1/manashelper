package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.entity.TelegramMessage;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;
import kg.manasuniversity.usbtypec.manashelper.mapper.LessonMapper;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.model.PeriodTimetable;
import kg.manasuniversity.usbtypec.manashelper.model.TimetableLessonChanges;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.LessonRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.TelegramMessageRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import tools.jackson.databind.cfg.MapperBuilder;

import java.time.LocalTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
public class LessonSynchronizeService {
  private static final Logger log = LoggerFactory.getLogger(LessonSynchronizeService.class);

  private final TimetableClient timetableClient;
  private final TimetableParser timetableParser;
  private final LessonRepository lessonRepository;
  private final CourseRepository courseRepository;
  private final UserRepository userRepository;
  private final TelegramMessageRepository telegramMessageRepository;
  private final LessonMapper lessonMapper;
  private final CourseLessonFormatter courseLessonFormatter;

  public LessonSynchronizeService(TimetableClient timetableClient, TimetableParser timetableParser,
                                  LessonRepository lessonRepository, CourseRepository courseRepository, UserRepository userRepository, TelegramMessageRepository telegramMessageRepository, LessonMapper lessonMapper, CourseLessonFormatter courseLessonFormatter) {
    this.timetableClient = timetableClient;
    this.timetableParser = timetableParser;
    this.lessonRepository = lessonRepository;
    this.courseRepository = courseRepository;
    this.userRepository = userRepository;
    this.telegramMessageRepository = telegramMessageRepository;
    this.lessonMapper = lessonMapper;
    this.courseLessonFormatter = courseLessonFormatter;
  }

  public void synchronizeLessons() {
    log.info("Starting lessons synchronization task");
    UUID newSynchronizationId = UUID.randomUUID();

    List<Course> courses = courseRepository.findAllWithDepartment();
    for (Course course : courses) {
      log.info("Fetching timetable for course ID: {}", course.getId());
      String html = timetableClient.fetchTimetableHtml(course.getId());
      CourseTimetableResponse timetableResponse = timetableParser.parse(course.getId(), html);

      // Get the last synchronization ID
      UUID lastSynchronizationId = lessonRepository
              .findTopByCourseOrderByCreatedAtDesc(course)
              .map(Lesson::getSynchronizationId)
              .orElse(null);

      // Get all lessons from the last synchronization
      List<Lesson> storedLessons = lastSynchronizationId != null
              ? lessonRepository.findByCourseAndSynchronizationIdWithCourse(course, lastSynchronizationId)
              : Collections.emptyList();

      // Build new lessons from the timetable response
      List<Lesson> newLessons = buildLessonsFromTimetable(course, timetableResponse, newSynchronizationId);

      TimetableLessonChanges timetableLessonChanges = getChanges(storedLessons, newLessons, course);

      boolean anyChanges = !timetableLessonChanges.addedLessons().isEmpty() || !timetableLessonChanges.removedLessons().isEmpty();

      if (anyChanges) {
        lessonRepository.saveAll(newLessons);

        for (var lesson : timetableLessonChanges.addedLessons()) {
          List<User> users = userRepository.findByCourses_Id(lesson.courseId());

          List<TelegramMessage> messages = users.stream().map(user -> {
            String messageText = courseLessonFormatter.formatAddedLesson(lesson);
            return new TelegramMessage(messageText, user.getId());
          }).toList();
          telegramMessageRepository.saveAll(messages);
        }

        for (var lesson : timetableLessonChanges.removedLessons()) {
          List<User> users = userRepository.findByCourses_Id(lesson.courseId());

          List<TelegramMessage> messages = users.stream().map(user -> {
            String messageText = courseLessonFormatter.formatRemovedLesson(lesson);
            return new TelegramMessage(messageText, user.getId());
          }).toList();
          telegramMessageRepository.saveAll(messages);
        }
      }
    }

    log.info("Lessons synchronization task completed");
  }

  private List<Lesson> buildLessonsFromTimetable(Course course, CourseTimetableResponse timetableResponse, UUID synchronizationId) {
    List<Lesson> lessons = new ArrayList<>();

    for (PeriodTimetable periodTimetable : timetableResponse.timetable()) {
      String[] startsAtAndEndsAt = periodTimetable.period().split("-");
      String[] startsAtHourAndMinute = startsAtAndEndsAt[0].split(":");
      String[] endsAtHourAndMinute = startsAtAndEndsAt[1].split(":");

      LocalTime startsAt = LocalTime.of(
              Integer.parseInt(startsAtHourAndMinute[0].trim()),
              Integer.parseInt(startsAtHourAndMinute[1].trim())
      );
      LocalTime endsAt = LocalTime.of(
              Integer.parseInt(endsAtHourAndMinute[0].trim()),
              Integer.parseInt(endsAtHourAndMinute[1].trim())
      );

      for (var lesson : periodTimetable.monday()) {
        lessons.add(new Lesson(
                synchronizationId,
                lesson.name(),
                course,
                lesson.teacherName(),
                lesson.location(),
                startsAt,
                endsAt,
                1,
                lesson.type()
        ));
      }

      for (var lesson : periodTimetable.tuesday()) {
        lessons.add(new Lesson(
                synchronizationId,
                lesson.name(),
                course,
                lesson.teacherName(),
                lesson.location(),
                startsAt,
                endsAt,
                2,
                lesson.type()
        ));
      }

      for (var lesson : periodTimetable.wednesday()) {
        lessons.add(new Lesson(
                synchronizationId,
                lesson.name(),
                course,
                lesson.teacherName(),
                lesson.location(),
                startsAt,
                endsAt,
                3,
                lesson.type()
        ));
      }

      for (var lesson : periodTimetable.thursday()) {
        lessons.add(new Lesson(
                synchronizationId,
                lesson.name(),
                course,
                lesson.teacherName(),
                lesson.location(),
                startsAt,
                endsAt,
                4,
                lesson.type()
        ));
      }

      for (var lesson : periodTimetable.friday()) {
        lessons.add(new Lesson(
                synchronizationId,
                lesson.name(),
                course,
                lesson.teacherName(),
                lesson.location(),
                startsAt,
                endsAt,
                5,
                lesson.type()
        ));
      }
    }

    return lessons;
  }

  private TimetableLessonChanges getChanges(List<Lesson> storedLessons, List<Lesson> newLessons, Course course) {
    Set<String> storedSignatures = storedLessons.stream()
            .map(this::createLessonSignature)
            .collect(Collectors.toSet());

    Set<String> newSignatures = newLessons.stream()
            .map(this::createLessonSignature)
            .collect(Collectors.toSet());

    List<CourseLesson> addedLessons = newLessons.stream()
            .filter(lesson -> !storedSignatures.contains(createLessonSignature(lesson)))
            .map(lesson -> lessonMapper.mapEntityAndCourseToCourseLesson(lesson, course))
            .collect(Collectors.toList());

    List<CourseLesson> removedLessons = storedLessons.stream()
            .filter(lesson -> !newSignatures.contains(createLessonSignature(lesson)))
            .map(lesson -> lessonMapper.mapEntityAndCourseToCourseLesson(lesson, course))
            .toList();

    return new TimetableLessonChanges(addedLessons, removedLessons);
  }

  private String createLessonSignature(Lesson lesson) {
    return String.join("|",
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