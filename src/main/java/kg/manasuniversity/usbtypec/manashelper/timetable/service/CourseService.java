package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.timetable.exception.DepartmentNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.timetable.mapper.CourseMapper;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.DepartmentCoursesResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.DepartmentRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class CourseService {
  private final DepartmentRepository departmentRepository;
  private final CourseRepository courseRepository;
  private final CourseMapper courseMapper;

  public CourseService(DepartmentRepository departmentRepository, CourseRepository courseRepository, CourseMapper courseMapper) {
    this.departmentRepository = departmentRepository;
    this.courseRepository = courseRepository;
    this.courseMapper = courseMapper;
  }

  public DepartmentCoursesResponse getCoursesByDepartmentId(UUID departmentId) {
    Department department = departmentRepository
            .findById(departmentId)
            .orElseThrow(() -> new DepartmentNotFoundException("Department not found with id: " + departmentId));
    List<Course> courses = courseRepository.findByDepartmentId(departmentId);
    List<DepartmentCoursesResponse.Course> departmentCourses = courses.stream().map(courseMapper::mapToDepartmentCoursesResponseCourse).toList();
    return new DepartmentCoursesResponse(
            department.getId(),
            department.getName(),
            department.getFaculty().getId(),
            department.getFaculty().getName(),
            departmentCourses
    );
  }
}
