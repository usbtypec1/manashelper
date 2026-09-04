package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.model.CourseTimetable;
import org.junit.jupiter.api.Test;
import org.mapstruct.factory.Mappers;

import java.time.LocalTime;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class LessonMapperTest {

    private final LessonMapper lessonMapper = Mappers.getMapper(LessonMapper.class);

    @Test
    void mapEntityAndCourseToCourseLesson_shouldMapAllFields() {
        Department department = new Department(UUID.randomUUID(), "Software Engineering", null);
        Course course = new Course(1, 2, department);
        Lesson lesson = Lesson.builder()
            .synchronizationId(UUID.randomUUID())
            .name("Databases")
            .course(course)
            .teacherName("John Doe")
            .location("Room 101")
            .startsAt(LocalTime.of(9, 0))
            .endsAt(LocalTime.of(10, 30))
            .weekday(1)
            .type(LessonType.MANDATORY_MAJOR)
            .build();

        CourseLesson courseLesson = lessonMapper.mapEntityAndCourseToCourseLesson(lesson, course);

        assertThat(courseLesson.departmentName()).isEqualTo("Software Engineering");
        assertThat(courseLesson.courseId()).isEqualTo(1);
        assertThat(courseLesson.courseNumber()).isEqualTo(2);
        assertThat(courseLesson.startsAt()).isEqualTo(LocalTime.of(9, 0));
        assertThat(courseLesson.endsAt()).isEqualTo(LocalTime.of(10, 30));
        assertThat(courseLesson.lessonName()).isEqualTo("Databases");
        assertThat(courseLesson.teacherName()).isEqualTo("John Doe");
        assertThat(courseLesson.location()).isEqualTo("Room 101");
        assertThat(courseLesson.type()).isEqualTo(LessonType.MANDATORY_MAJOR);
        assertThat(courseLesson.weekday()).isEqualTo(1);
    }

    @Test
    void mapResponseLessonToEntity_shouldMapAllFieldsAndIgnoreGeneratedOnes() {
        Department department = new Department(UUID.randomUUID(), "Software Engineering", null);
        Course course = new Course(1, 2, department);
        CourseTimetable responseLesson = new CourseTimetable(
            1,
            "Databases",
            "John Doe",
            "Room 101",
            LocalTime.of(9, 0),
            LocalTime.of(10, 30),
            1,
            LessonType.MANDATORY_MAJOR
        );
        UUID synchronizationId = UUID.randomUUID();

        Lesson lesson = lessonMapper.mapResponseLessonToEntity(responseLesson, course, synchronizationId);

        assertThat(lesson.getId()).isNull();
        assertThat(lesson.getCreatedAt()).isNull();
        assertThat(lesson.getSynchronizationId()).isEqualTo(synchronizationId);
        assertThat(lesson.getName()).isEqualTo("Databases");
        assertThat(lesson.getCourse()).isEqualTo(course);
        assertThat(lesson.getTeacherName()).isEqualTo("John Doe");
        assertThat(lesson.getLocation()).isEqualTo("Room 101");
        assertThat(lesson.getStartsAt()).isEqualTo(LocalTime.of(9, 0));
        assertThat(lesson.getEndsAt()).isEqualTo(LocalTime.of(10, 30));
        assertThat(lesson.getWeekday()).isEqualTo(1);
        assertThat(lesson.getType()).isEqualTo(LessonType.MANDATORY_MAJOR);
    }
}
