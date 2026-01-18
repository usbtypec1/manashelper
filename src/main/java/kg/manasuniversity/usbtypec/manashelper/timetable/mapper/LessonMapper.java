package kg.manasuniversity.usbtypec.manashelper.timetable.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.CourseTimetableResponse;
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

  public CourseTimetableResponse mapEntityToResponseLesson(Lesson lesson) {
    return new CourseTimetableResponse(
            lesson.getCourse().getId(),
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
          CourseTimetableResponse responseLesson,
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
