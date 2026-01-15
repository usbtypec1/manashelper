package kg.manasuniversity.usbtypec.manashelper.timetable.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.UserTrackingCourseResponse;
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
