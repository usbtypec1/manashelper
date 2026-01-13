package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenuRating;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface DailyMenuRatingRepository extends JpaRepository<DailyMenuRating, UUID> {
}
