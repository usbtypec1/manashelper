package kg.manasuniversity.usbtypec.manashelper.controller.api;

import jakarta.validation.Valid;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.service.ObisService;
import kg.manasuniversity.usbtypec.manashelper.service.UserService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserController {
  private final UserService userService;
  private final ObisService obisService;

  public UserController(
          UserService userService,
          ObisService obisService
  ) {
    this.userService = userService;
    this.obisService = obisService;
  }

  @PostMapping
  public ResponseEntity<Void> upsertUser(
          @Valid @RequestBody UserUpsertRequest userRequest
  ) {
    try {
      userService.upsertUser(userRequest);
      return ResponseEntity.ok().build();
    } catch (Exception e) {
      e.printStackTrace();
      return ResponseEntity.internalServerError().build();
    }
  }

  @GetMapping("/{id}/attendance")
  public ResponseEntity<List<LessonAttendance>> getLessonAttendanceByUserId(
          @PathVariable long id
  ) {
    try {
      List<LessonAttendance> responseData = obisService.getUserAttendance(id);
      return ResponseEntity.ok(responseData);
    } catch (UserNotFoundException e) {
      return ResponseEntity.notFound().build();
    }
  }

  @GetMapping("/{id}/grades")
  public ResponseEntity<List<LessonExams>> getLessonGradesByUserId(
          @PathVariable long id
  ) {
    try {
      List<LessonExams> responseData = obisService.getUserExamGrades(id);
      return ResponseEntity.ok(responseData);
    } catch (UserNotFoundException e) {
      return ResponseEntity.notFound().build();
    }
  }
}
