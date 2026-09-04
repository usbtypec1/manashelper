package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.model.DepartmentSummary;
import kg.manasuniversity.usbtypec.manashelper.repository.DepartmentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class DepartmentService {
    private final DepartmentRepository departmentRepository;

    public List<DepartmentSummary> getDepartmentsByFaculty(UUID facultyId) {
        return departmentRepository.findAllByFacultyId(facultyId).stream()
            .map(this::toSummary)
            .toList();
    }

    private DepartmentSummary toSummary(Department department) {
        return new DepartmentSummary(department.getId(), department.getName());
    }
}
