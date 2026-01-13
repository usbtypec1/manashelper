package kg.manasuniversity.usbtypec.manashelper.payload.response;

import java.util.List;
import java.util.UUID;

public record FacultyDepartmentResponse(
        UUID facultyId,
        String facultyName,
        List<Department> departments
) {
  public record Department(
          UUID id,
          String name
  ) {
  }
}
