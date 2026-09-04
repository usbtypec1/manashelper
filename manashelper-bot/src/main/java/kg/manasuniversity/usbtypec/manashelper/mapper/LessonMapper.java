package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.model.CourseTimetable;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

import java.util.UUID;

@Mapper(componentModel = "spring")
public interface LessonMapper {

    @Mapping(target = "departmentName", source = "course.department.name")
    @Mapping(target = "courseId", source = "course.id")
    @Mapping(target = "courseNumber", source = "course.number")
    @Mapping(target = "lessonName", source = "lesson.name")
    CourseLesson mapEntityAndCourseToCourseLesson(Lesson lesson, Course course);

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    Lesson mapResponseLessonToEntity(CourseTimetable responseLesson, Course course, UUID synchronizationId);
}
