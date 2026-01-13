package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.payload.response.DepartmentCoursesResponse;
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
