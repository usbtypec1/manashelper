package kg.manasuniversity.usbtypec.manashelper.foodmenu.repository;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.Dish;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface DishRepository extends JpaRepository<Dish, UUID> {
    Optional<Dish> findByName(String name);
}
