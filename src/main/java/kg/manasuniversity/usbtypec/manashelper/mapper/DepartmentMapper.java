package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.payload.response.FacultyDepartmentResponse;
import org.springframework.stereotype.Component;

@Component
public class DepartmentMapper {
  public FacultyDepartmentResponse.Department mapDepartmentEntityToResponse(Department department) {
    return new FacultyDepartmentResponse.Department(department.getId(), department.getName());
  }
}
