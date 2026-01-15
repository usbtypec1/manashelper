package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import org.junit.jupiter.api.Test;

import java.time.LocalTime;

import static org.assertj.core.api.Assertions.assertThat;

class CourseLessonFormatterTest {

  private final CourseLessonFormatter formatter = new CourseLessonFormatter();

  @Test
  void formatsAddedLesson() {
    CourseLesson lesson = new CourseLesson(
            "Engineering",
            101,
            1,
            LocalTime.of(9, 0),
            LocalTime.of(10, 30),
            "Algorithms",
            "Dr. Ada",
            "Room 12",
            LessonType.MANDATORY_MAJOR,
            1
    );

    String message = formatter.formatAddedLesson(lesson);

    assertThat(message).contains("✅ <b>Новый урок:</b> Algorithms (Обязательный (профильный))");
    assertThat(message).contains("🧑‍🏫 <b>Преподаватель:</b> Dr. Ada");
    assertThat(message).contains("📍 <b>Место:</b> Room 12");
    assertThat(message).contains("🗓 Понедельник в 09:00-10:30.");
  }

  @Test
  void formatsRemovedLesson() {
    CourseLesson lesson = new CourseLesson(
            "Engineering",
            202,
            2,
            LocalTime.of(13, 15),
            LocalTime.of(14, 45),
            "Databases",
            "Dr. Codd",
            "Room 34",
            LessonType.ELECTIVE_OTHER,
            5
    );

    String message = formatter.formatRemovedLesson(lesson);

    assertThat(message).contains("❌ <b>Удален урок:</b> Databases (Выборочный (общий))");
    assertThat(message).contains("🧑‍🏫 <b>Преподаватель:</b> Dr. Codd");
    assertThat(message).contains("📍 <b>Место:</b> Room 34");
    assertThat(message).contains("🗓 Пятница в 13:15-14:45.");
  }
}
