package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.exception.CourseNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.mapper.LessonMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.LessonRepository;
import org.springframework.stereotype.Service;

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

  public CourseTimetableResponse getCourseTimetable(int courseId) {
    Course course = courseRepository
            .findByIdWithDepartment(courseId)
            .orElseThrow(() -> new CourseNotFoundException("Course with id " + courseId + " not found"));

    Lesson lesson = lessonRepository
            .findTopByCourseOrderByCreatedAtDesc(course)
            .orElseThrow(() -> new CourseNotFoundException("Course with id " + courseId + " not found"));

    List<Lesson> lessons = lessonRepository
            .findByCourseAndSynchronizationIdWithCourse(course, lesson.getSynchronizationId());

    List<CourseTimetableResponse.Lesson> responseLessons = lessons
            .stream()
            .map(lessonMapper::mapEntityToResponseLesson)
            .toList();

    return new CourseTimetableResponse(course.getId(), responseLessons);
  }
}
