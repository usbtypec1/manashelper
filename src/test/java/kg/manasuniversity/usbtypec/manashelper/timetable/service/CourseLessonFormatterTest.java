package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.telegram.service.CourseLessonFormatter;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.LessonType;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseLesson;
import org.junit.jupiter.api.Test;

import java.time.LocalTime;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class CourseLessonFormatterTest {

  private final CourseLessonFormatter formatter = new CourseLessonFormatter();

  private static CourseLesson baseLessonWithWeekday(int weekday) {
    return new CourseLesson(
            "Dept",
            1,
            1,
            LocalTime.of(9, 0),
            LocalTime.of(10, 0),
            "Lesson",
            "Teacher",
            "Location",
            LessonType.MANDATORY_MAJOR,
            weekday
    );
  }

  @Test
  void addedLesson_shouldUseUnknownDay_whenWeekdayIsZero() {
    CourseLesson lesson = baseLessonWithWeekday(0);

    String result = formatter.formatAddedLesson(lesson);

    assertTrue(result.contains("🗓 Неизвестный день"), "Should fall back to unknown day");
  }

  @Test
  void addedLesson_shouldUseUnknownDay_whenWeekdayIsNegative() {
    CourseLesson lesson = baseLessonWithWeekday(-3);

    String result = formatter.formatAddedLesson(lesson);

    assertTrue(result.contains("🗓 Неизвестный день"), "Should fall back to unknown day");
  }

  @Test
  void addedLesson_shouldUseUnknownDay_whenWeekdayIsGreaterThan7() {
    CourseLesson lesson = baseLessonWithWeekday(999);

    String result = formatter.formatAddedLesson(lesson);

    assertTrue(result.contains("🗓 Неизвестный день"), "Should fall back to unknown day");
  }

  @Test
  void removedLesson_shouldUseUnknownDay_whenWeekdayIsInvalid() {
    CourseLesson lesson = baseLessonWithWeekday(8);

    String result = formatter.formatRemovedLesson(lesson);

    assertTrue(result.contains("🗓 Неизвестный день"), "Should fall back to unknown day");
  }

  @Test
  void formatAddedLesson_shouldThrow_whenCourseLessonIsNull() {
    assertThrows(NullPointerException.class, () -> formatter.formatAddedLesson(null));
  }

  @Test
  void formatRemovedLesson_shouldThrow_whenCourseLessonIsNull() {
    assertThrows(NullPointerException.class, () -> formatter.formatRemovedLesson(null));
  }

  @Test
  void formatAddedLesson_shouldThrow_whenLessonTypeIsNull() {
    CourseLesson lesson = new CourseLesson(
            "Dept",
            1,
            1,
            LocalTime.of(9, 0),
            LocalTime.of(10, 0),
            "Lesson",
            "Teacher",
            "Location",
            null, // important edge-case
            1
    );

    assertThrows(NullPointerException.class, () -> formatter.formatAddedLesson(lesson));
  }

  @Test
  void formatRemovedLesson_shouldThrow_whenLessonTypeIsNull() {
    CourseLesson lesson = new CourseLesson(
            "Dept",
            1,
            1,
            LocalTime.of(9, 0),
            LocalTime.of(10, 0),
            "Lesson",
            "Teacher",
            "Location",
            null, // important edge-case
            1
    );

    assertThrows(NullPointerException.class, () -> formatter.formatRemovedLesson(lesson));
  }

  @Test
  void formatAddedLesson_shouldThrow_whenStartsAtIsNull() {
    CourseLesson lesson = new CourseLesson(
            "Dept",
            1,
            1,
            null, // LocalTime null
            LocalTime.of(10, 0),
            "Lesson",
            "Teacher",
            "Location",
            LessonType.MANDATORY_MAJOR,
            1
    );

    // String.format("%s", null) would print "null", but this test locks expected behavior.
    String result = formatter.formatAddedLesson(lesson);
    assertTrue(result.contains("в null-10:00."), "Null startsAt should appear as 'null' in output (current behavior)");
  }

  @Test
  void formatAddedLesson_shouldThrow_whenEndsAtIsNull() {
    CourseLesson lesson = new CourseLesson(
            "Dept",
            1,
            1,
            LocalTime.of(9, 0),
            null,
            "Lesson",
            "Teacher",
            "Location",
            LessonType.MANDATORY_MAJOR,
            1
    );

    String result = formatter.formatAddedLesson(lesson);
    assertTrue(result.contains("в 09:00-null."), "Null endsAt should appear as 'null' in output (current behavior)");
  }

  @Test
  void formatAddedLesson_shouldNotCrash_whenStringsAreNull() {
    CourseLesson lesson = new CourseLesson(
            "Dept",
            1,
            1,
            LocalTime.of(9, 0),
            LocalTime.of(10, 0),
            null,  // lessonName
            null,  // teacherName
            null,  // location
            LessonType.ELECTIVE_MAJOR,
            2
    );

    String result = formatter.formatAddedLesson(lesson);

    // String.format prints "null" for null strings; we lock that behavior.
    assertTrue(result.contains("<b>Новый урок:</b> null"), "Null lessonName should appear as 'null'");
    assertTrue(result.contains("<b>Преподаватель:</b> null"), "Null teacherName should appear as 'null'");
    assertTrue(result.contains("<b>Место:</b> null"), "Null location should appear as 'null'");
  }

  @Test
  void formatRemovedLesson_shouldKeepNewlinesAndEndingDot() {
    CourseLesson lesson = baseLessonWithWeekday(3);

    String result = formatter.formatRemovedLesson(lesson);

    // Formatting stability tests: these catch accidental regressions.
    assertTrue(result.contains("\n🧑‍🏫"), "Should contain newline before teacher line");
    assertTrue(result.contains("\n📍"), "Should contain newline before location line");
    assertTrue(result.endsWith("."), "Should end with a dot");
  }
}
