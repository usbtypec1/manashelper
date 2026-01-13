package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.exception.FacultyNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.mapper.DepartmentMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.response.FacultyDepartmentResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.DepartmentRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.FacultyRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class DepartmentService {
  private final DepartmentRepository departmentRepository;
  private final DepartmentMapper departmentMapper;
  private final FacultyRepository facultyRepository;

  public DepartmentService(DepartmentRepository departmentRepository, DepartmentMapper departmentMapper, FacultyRepository facultyRepository) {
    this.departmentRepository = departmentRepository;
    this.departmentMapper = departmentMapper;
    this.facultyRepository = facultyRepository;
  }

  public FacultyDepartmentResponse getDepartmentsByFacultyId(UUID facultyId) {
    Faculty faculty = facultyRepository
            .findById(facultyId)
            .orElseThrow(() -> new FacultyNotFoundException("Faculty not found with id: " + facultyId));
    List<Department> departments = departmentRepository.findByFacultyId(facultyId);
    List<FacultyDepartmentResponse.Department> facultyDepartments = departments
            .stream()
            .map(departmentMapper::mapDepartmentEntityToResponse)
            .toList();
    return new FacultyDepartmentResponse(faculty.getId(), faculty.getName(), facultyDepartments);
  }
}
