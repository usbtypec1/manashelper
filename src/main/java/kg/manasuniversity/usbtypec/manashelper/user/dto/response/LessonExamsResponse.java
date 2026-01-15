package kg.manasuniversity.usbtypec.manashelper.user.dto.response;

import java.util.List;

public record LessonExamsResponse(
        String lessonName,
        String lessonCode,
        List<Exam> exams
) {
  public record Exam(
          String name,
          String score
  ) {
  }
}
