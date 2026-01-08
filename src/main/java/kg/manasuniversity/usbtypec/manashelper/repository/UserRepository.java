package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
}
