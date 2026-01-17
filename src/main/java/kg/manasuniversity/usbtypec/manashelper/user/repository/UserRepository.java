package kg.manasuniversity.usbtypec.manashelper.user.repository;

import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
  @Query("""
          SELECT DISTINCT u
          FROM User u
            LEFT JOIN FETCH u.courses c
            LEFT JOIN FETCH c.department
          WHERE u.id = :userId
          """)
  Optional<User> findByIdWithCoursesAndDepartments(@Param("userId") long userId);

  List<User> findByCourses_Id(Integer courseId);

  int countByStudentNumberIsNotNullAndEncryptedPasswordIsNotNull();
}
