package kg.manasuniversity.usbtypec.manashelper.timetable.repository;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Faculty;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface FacultyRepository extends JpaRepository<Faculty, UUID> {
}
