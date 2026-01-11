package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Lesson;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface LessonRepository extends JpaRepository<Lesson, Integer> {

  Optional<Lesson> findTopByCourseOrderByCreatedAtDesc(Course course);

  List<Lesson> findByCourseAndSynchronizationId(Course course, UUID synchronizationId);
}
