package kg.manasuniversity.usbtypec.manashelper.timetable.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseTimetable;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseLesson;
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

    public Lesson mapResponseLessonToEntity(
        CourseTimetable responseLesson,
        Course course,
        UUID synchronizationId) {
        return Lesson.builder()
            .synchronizationId(synchronizationId)
            .name(responseLesson.name())
            .course(course)
            .teacherName(responseLesson.teacherName())
            .location(responseLesson.location())
            .startsAt(responseLesson.startsAt())
            .endsAt(responseLesson.endsAt())
            .weekday(responseLesson.weekday())
            .type(responseLesson.type())
            .build();
    }
}
