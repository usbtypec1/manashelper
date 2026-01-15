package kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.repository;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.entity.DailyMenu;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;

public interface DailyMenuRepository extends JpaRepository<DailyMenu, UUID> {
  Optional<DailyMenu> findByDate(LocalDate date);
}
