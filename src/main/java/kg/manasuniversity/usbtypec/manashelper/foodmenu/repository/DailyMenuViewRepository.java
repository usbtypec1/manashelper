package kg.manasuniversity.usbtypec.manashelper.foodmenu.repository;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenuView;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface DailyMenuViewRepository extends JpaRepository<DailyMenuView, UUID> {
    int countByMenuId(UUID menuId);
}
