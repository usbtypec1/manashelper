package kg.manasuniversity.usbtypec.manashelper.timetable.repository;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Department;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface DepartmentRepository extends JpaRepository<Department, UUID> {
    List<Department> findAllByFacultyId(UUID facultyId);
}
