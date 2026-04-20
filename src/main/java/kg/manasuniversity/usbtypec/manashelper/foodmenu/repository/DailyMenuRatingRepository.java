package kg.manasuniversity.usbtypec.manashelper.foodmenu.repository;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenuRating;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface DailyMenuRatingRepository extends JpaRepository<DailyMenuRating, UUID> {

    @Query("""
        SELECT dmr FROM DailyMenuRating dmr
        JOIN FETCH dmr.user
        WHERE dmr.dailyMenu.id = :dailyMenu
        """)
    List<DailyMenuRating> findByDailyMenuIdWithUser(@Param("dailyMenu") UUID dailyMenu);

    Optional<DailyMenuRating> findByUserIdAndDailyMenuId(Long userId, UUID dailyMenuId);
}
