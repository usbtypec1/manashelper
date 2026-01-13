package kg.manasuniversity.usbtypec.manashelper.payload.response;

import java.util.List;
import java.util.UUID;

public record DepartmentCoursesResponse(
        UUID departmentId,
        String departmentName,
        UUID facultyId,
        String facultyName,
        List<Course> courses
) {
  public record Course(
          int id,
          int number
  ) {
  }
}
