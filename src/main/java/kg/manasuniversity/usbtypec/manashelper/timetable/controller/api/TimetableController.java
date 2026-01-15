package kg.manasuniversity.usbtypec.manashelper.timetable.controller.api;

import jakarta.validation.Valid;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.request.UserTimetableTrackerUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.DepartmentCoursesResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.FacultyDepartmentResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.FacultyResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.UserTrackingCourseResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.CourseService;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.DepartmentService;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.FacultyService;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.TimetableService;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.LessonService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/timetable")
public class TimetableController {
  private final LessonService lessonService;
  private final FacultyService facultyService;
  private final DepartmentService departmentService;
  private final TimetableService timetableService;
  private final CourseService courseService;

  public TimetableController(LessonService lessonService, FacultyService facultyService, DepartmentService departmentService, TimetableService timetableService, CourseService courseService) {
    this.lessonService = lessonService;
    this.facultyService = facultyService;
    this.departmentService = departmentService;
    this.timetableService = timetableService;
    this.courseService = courseService;
  }

  @GetMapping
  public CourseTimetableResponse getTimetable(
          @RequestParam(name = "courseId") int courseId
  ) {
    return lessonService.getCourseTimetable(courseId);
  }

  @GetMapping("/faculties")
  public List<FacultyResponse> getAllFaculties() {
    return facultyService.getAllFaculties();
  }

  @GetMapping("/departments")
  public FacultyDepartmentResponse getDepartmentsByFaculty(@RequestParam(name = "facultyId") UUID facultyId) {
    return departmentService.getDepartmentsByFacultyId(facultyId);
  }

  @GetMapping("/courses")
  public DepartmentCoursesResponse getCoursesByDepartment(@RequestParam(name = "departmentId") UUID departmentId) {
    return courseService.getCoursesByDepartmentId(departmentId);
  }

  @GetMapping("/tracking/users/{userId}")
  public UserTrackingCourseResponse getUserTimetableTracking(
          @PathVariable long userId
  ) {
    return timetableService.getUserTrackingCourses(userId);
  }

  @PutMapping("/tracking/users/{id}")
  public ResponseEntity<Void> updateTimetableTracking(
          @PathVariable long id,
          @Valid @RequestBody UserTimetableTrackerUpdateRequest requestData
  ) {
    timetableService.updateUserTrackingCourses(id, requestData.courseIds());
    return ResponseEntity.noContent().build();
  }
}
