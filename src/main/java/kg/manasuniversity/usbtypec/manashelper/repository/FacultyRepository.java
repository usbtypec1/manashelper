package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.Faculty;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.UUID;

@Repository
public interface FacultyRepository extends JpaRepository<Faculty, UUID> {
}
