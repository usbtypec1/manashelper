package kg.manasuniversity.usbtypec.manashelper.user.controller.api;

import kg.manasuniversity.usbtypec.manashelper.user.dto.response.LessonAttendanceResponse;
import kg.manasuniversity.usbtypec.manashelper.user.dto.response.LessonExamsResponse;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.user.service.ObisService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserStudentAccountController {
  private final ObisService obisService;

  public UserStudentAccountController(ObisService obisService) {
    this.obisService = obisService;
  }

  @GetMapping("/{id}/attendance")
  public ResponseEntity<List<LessonAttendanceResponse>> getLessonAttendanceByUserId(
          @PathVariable long id
  ) {
    var responseData = obisService.getUserAttendance(id);
    return ResponseEntity.ok(responseData);
  }

  @GetMapping("/{id}/exams")
  public ResponseEntity<List<LessonExamsResponse>> getLessonGradesByUserId(
          @PathVariable long id
  ) {
    var responseData = obisService.getUserExamGrades(id);
    return ResponseEntity.ok(responseData);
  }
}
