package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface CourseRepository extends JpaRepository<Course, Integer> {
}
