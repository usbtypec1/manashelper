package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface LessonRepository extends JpaRepository<Lesson, Integer> {

    Optional<Lesson> findTopByCourseOrderByCreatedAtDesc(Course course);

    @Query("""
        SELECT l
        FROM Lesson l
          LEFT JOIN FETCH l.course c
        WHERE l.course = :course AND l.synchronizationId = :synchronizationId
        """)
    List<Lesson> findByCourseAndSynchronizationIdWithCourse(
        @Param("course") Course course,
        @Param("synchronizationId") UUID synchronizationId
    );
}
