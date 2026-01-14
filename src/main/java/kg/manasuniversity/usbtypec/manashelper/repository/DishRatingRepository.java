package kg.manasuniversity.usbtypec.manashelper.repository;

import kg.manasuniversity.usbtypec.manashelper.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.entity.DishRating;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface DishRatingRepository extends JpaRepository<DishRating, Integer> {
  Optional<DishRating> findByDishAndUser(Dish dish, User user);
}
