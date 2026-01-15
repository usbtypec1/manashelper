package kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dish.repository;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dish.entity.DishRating;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface DishRatingRepository extends JpaRepository<DishRating, Integer> {
  Optional<DishRating> findByDishAndUser(Dish dish, User user);
}
