package kg.manasuniversity.usbtypec.manashelper.timetable.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.DepartmentCoursesResponse;
import org.springframework.stereotype.Component;

@Component
public class CourseMapper {
  public DepartmentCoursesResponse.Course mapToDepartmentCoursesResponseCourse(
          Course course
  ) {
    return new DepartmentCoursesResponse.Course(
            course.getId(),
            course.getNumber()
    );
  }
}
