package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.payload.response.UserTrackingCourseResponse;
import org.springframework.stereotype.Component;

@Component
public class TimetableMapper {
  public UserTrackingCourseResponse.Course mapToUserTrackingCourseResponseCourse(Course course) {
    return new UserTrackingCourseResponse.Course(
            course.getId(),
            course.getNumber(),
            course.getDepartment().getName()
    );
  }
}
