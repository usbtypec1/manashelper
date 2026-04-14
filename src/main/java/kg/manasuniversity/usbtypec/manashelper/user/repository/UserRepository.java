package kg.manasuniversity.usbtypec.manashelper.user.repository;

import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.Optional;

public interface UserRepository extends JpaRepository<User, Long> {

    @EntityGraph(attributePaths = "courses")
    @Query("select u from User u where u.id = :userId")
    Optional<User> findByIdWithCourses(Long userId);
}
