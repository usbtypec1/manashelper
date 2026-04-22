package kg.manasuniversity.usbtypec.manashelper.foodmenu.repository;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenuView;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDateTime;
import java.util.UUID;

public interface DailyMenuViewRepository extends JpaRepository<DailyMenuView, UUID> {
    int countByMenuId(UUID menuId);

    int countByMenuIdAndCreatedAtBetween(UUID menuId, LocalDateTime from, LocalDateTime to);
}
