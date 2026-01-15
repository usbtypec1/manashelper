package kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.service;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dish.dto.request.DishRatingUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dish.entity.DishRating;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.exception.DishNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dish.repository.DishRatingRepository;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.repository.DishRepository;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Objects;
import java.util.UUID;

@Service
public class DishService {

  private final DishRepository dishRepository;
  private final DishRatingRepository dishRatingRepository;
  private final UserRepository userRepository;

  public DishService(
          DishRepository dishRepository,
          DishRatingRepository dishRatingRepository,
          UserRepository userRepository
  ) {
    this.dishRepository = dishRepository;
    this.dishRatingRepository = dishRatingRepository;
    this.userRepository = userRepository;
  }

  @Transactional
  public void updateDishRating(UUID dishId, DishRatingUpdateRequest requestBody) {
    if (!dishRepository.existsById(dishId)) {
      throw new DishNotFoundException("Dish not found with id: " + dishId);
    }
    if (!userRepository.existsById(requestBody.userId())) {
      throw new UserNotFoundException("User not found with id: " + requestBody.userId());
    }

    Dish dish = dishRepository.getReferenceById(dishId);
    User user = userRepository.getReferenceById(requestBody.userId());

    DishRating rating = dishRatingRepository
            .findByDishAndUser(dish, user)
            .orElse(null);

    if (rating != null) {
      boolean sameScore = Objects.equals(rating.getScore(), requestBody.score());
      boolean sameComment = Objects.equals(rating.getComment(), requestBody.comment());

      if (sameScore && sameComment) {
        return;
      }
      rating.setScore(requestBody.score());
      rating.setComment(requestBody.comment());
      dishRatingRepository.save(rating);
    } else {
      rating = new DishRating(dish, user, requestBody.score(), requestBody.comment());
      dishRatingRepository.save(rating);
    }
  }
}
