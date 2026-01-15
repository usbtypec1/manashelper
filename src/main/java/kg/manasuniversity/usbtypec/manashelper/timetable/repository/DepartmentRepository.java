package kg.manasuniversity.usbtypec.manashelper.timetable.repository;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Department;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DepartmentRepository extends JpaRepository<Department, UUID> {
  List<Department> findByFacultyId(UUID facultyId);

  @Query("""
          SELECT d
          FROM Department d
            LEFT JOIN FETCH d.faculty f
          WHERE d.id = :departmentId
          """)
  Optional<Department> findByIdWithFaculty(@Param("departmentId") UUID departmentId);
}
