package kg.manasuniversity.usbtypec.manashelper.user.mapper;

import kg.manasuniversity.usbtypec.manashelper.user.dto.response.LessonExamsResponse;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.Exam;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.LessonExams;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class LessonExamsMapper {

  public LessonExamsResponse.Exam mapToResponseExam(Exam exam) {
    return new LessonExamsResponse.Exam(exam.name(), exam.score());
  }

  public LessonExamsResponse mapToResponse(LessonExams lessonExams) {
    List<LessonExamsResponse.Exam> exams = lessonExams.exams().stream()
            .map(this::mapToResponseExam)
            .toList();
    return new LessonExamsResponse(lessonExams.lessonName(), lessonExams.lessonCode(), exams);
  }
}
