package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DailyMenuRatingRepository extends JpaRepository<DailyMenuRating, UUID> {
  Optional<DailyMenuRating> findByDailyMenuAndUser(DailyMenu dailyMenu, User user);

  List<DailyMenuRating> findByDailyMenu(DailyMenu dailyMenu);

  Optional<DailyMenuRating> findByDailyMenu_IdAndUser_Id(UUID dailyMenuId, long userId);
}
