package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import org.springframework.stereotype.Component;

import java.util.UUID;

@Component
public class LessonMapper {
  public CourseLesson mapEntityAndCourseToCourseLesson(Lesson lesson, Course course) {
    return new CourseLesson(
            course.getDepartment().getName(),
            course.getId(),
            course.getNumber(),
            lesson.getStartsAt(),
            lesson.getEndsAt(),
            lesson.getName(),
            lesson.getTeacherName(),
            lesson.getLocation(),
            lesson.getType(),
            lesson.getWeekday()
    );
  }

  public CourseTimetableResponse.Lesson mapEntityToResponseLesson(Lesson lesson) {
    return new CourseTimetableResponse.Lesson(
            lesson.getName(),
            lesson.getTeacherName(),
            lesson.getLocation(),
            lesson.getStartsAt(),
            lesson.getEndsAt(),
            lesson.getWeekday(),
            lesson.getType()
    );
  }

  public Lesson mapResponseLessonToEntity(
          CourseTimetableResponse.Lesson responseLesson,
          Course course,
          UUID synchronizationId) {
    return new Lesson(
            synchronizationId,
            responseLesson.name(),
            course,
            responseLesson.teacherName(),
            responseLesson.location(),
            responseLesson.startsAt(),
            responseLesson.endsAt(),
            responseLesson.weekday(),
            responseLesson.type()
    );
  }
}
