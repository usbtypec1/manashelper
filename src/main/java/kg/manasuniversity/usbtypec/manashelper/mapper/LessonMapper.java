package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import org.springframework.stereotype.Component;

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
}
