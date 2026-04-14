package kg.manasuniversity.usbtypec.manashelper.timetable.repository;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.UUID;

public interface CourseRepository extends JpaRepository<Course, Integer> {

    @EntityGraph(attributePaths = "department")
    List<Course> findAllByDepartmentId(UUID departmentId);

    @Query("""
               SELECT c
               FROM Course c
               LEFT JOIN FETCH c.department d
        """)
    List<Course> findAllWithDepartment();

    @Query("""
               SELECT c
               FROM Course c
               LEFT JOIN FETCH c.department d
               WHERE c.id IN :ids
        """)
    List<Course> findByIdInWithDepartment(List<Integer> ids);
}
