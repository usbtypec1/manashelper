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

  @Query("""
          SELECT dmr FROM DailyMenuRating dmr
          JOIN FETCH dmr.user
          WHERE dmr.dailyMenu.id = :dailyMenu
          """)
  List<DailyMenuRating> findByDailyMenu_IdWithUser(UUID dailyMenu);

  @Query("""
          SELECT dmr FROM DailyMenuRating dmr
          JOIN FETCH dmr.user
          WHERE dmr.dailyMenu.id = :dailyMenuId AND dmr.user.id = :userId
          """)
  List<DailyMenuRating> findByDailyMenu_IdAndUser_IdWithUser(UUID dailyMenuId, long userId);
}
