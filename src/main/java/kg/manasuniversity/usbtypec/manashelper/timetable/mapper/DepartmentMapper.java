package kg.manasuniversity.usbtypec.manashelper.timetable.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.FacultyDepartmentResponse;
import org.springframework.stereotype.Component;

@Component
public class DepartmentMapper {
  public FacultyDepartmentResponse.Department mapDepartmentEntityToResponse(Department department) {
    return new FacultyDepartmentResponse.Department(department.getId(), department.getName());
  }
}
