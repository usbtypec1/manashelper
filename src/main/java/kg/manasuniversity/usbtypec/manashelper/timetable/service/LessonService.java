package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.mapper.LessonMapper;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.LessonRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class LessonService {
  private final LessonRepository lessonRepository;
  private final CourseRepository courseRepository;
  private final LessonMapper lessonMapper;

  public LessonService(LessonRepository lessonRepository, CourseRepository courseRepository, LessonMapper lessonMapper) {
    this.lessonRepository = lessonRepository;
    this.courseRepository = courseRepository;
    this.lessonMapper = lessonMapper;
  }

  public List<CourseTimetableResponse> getCourseTimetable(List<Integer> courseIds) {
    List<Course> courses = courseRepository.findByIdInWithDepartment(courseIds);

    List<CourseTimetableResponse> result = new ArrayList<>();

    for (var course : courses) {
      Lesson lesson = lessonRepository
              .findTopByCourseOrderByCreatedAtDesc(course)
              .orElse(null);
      if (lesson == null) {
        continue;
      }

      List<Lesson> lessons = lessonRepository
              .findByCourseAndSynchronizationIdWithCourse(course, lesson.getSynchronizationId());

      List<CourseTimetableResponse> responseLessons = lessons
              .stream()
              .map(lessonMapper::mapEntityToResponseLesson)
              .toList();
      result.addAll(responseLessons);
    }
    return result;
  }
}
