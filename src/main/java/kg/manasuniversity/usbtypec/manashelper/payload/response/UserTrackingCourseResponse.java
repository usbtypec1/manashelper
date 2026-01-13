package kg.manasuniversity.usbtypec.manashelper.payload.response;

import java.util.List;

public record UserTrackingCourseResponse(
        Long userId,
        List<Course> courses
) {
  public record Course(Integer id, Integer number, String departmentName) {}
}
