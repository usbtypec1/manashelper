package kg.manasuniversity.usbtypec.manashelper.controller.api;

import jakarta.validation.Valid;
import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.payload.request.RatingUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.payload.response.DailyMenuRatingResponse;
import kg.manasuniversity.usbtypec.manashelper.service.food_menu.DailyMenuService;
import kg.manasuniversity.usbtypec.manashelper.service.food_menu.DishService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.UUID;

@RestController
@RequestMapping("/api/food-menu")
public class FoodMenuController {
  private final DailyMenuService dailyMenuService;
  private final DishService dishService;

  public FoodMenuController(DailyMenuService dailyMenuService, DishService dishService) {
    this.dailyMenuService = dailyMenuService;
    this.dishService = dishService;
  }

  @GetMapping
  public DailyMenu getDailyMenuList(@RequestParam(name = "date") LocalDate date) {
    return dailyMenuService.getDailyMenuByDate(date);
  }

  @GetMapping("/{dailyMenuId}/ratings/users/{userId}")
  public ResponseEntity<DailyMenuRatingResponse> getDailyMenuRating(
          @PathVariable UUID dailyMenuId,
          @PathVariable long userId
  ) {
    DailyMenuRatingResponse rating = dailyMenuService.getDailyMenuRating(dailyMenuId, userId);
    return ResponseEntity.ok(rating);
  }

  @PutMapping("/{dailyMenuId}/ratings")
  public ResponseEntity<Void> updateDailyMenuRating(
          @PathVariable UUID dailyMenuId,
          @Valid @RequestBody RatingUpdateRequest requestBody
  ) {
    dailyMenuService.updateDailyMenuRating(dailyMenuId, requestBody);
    return ResponseEntity.noContent().build();
  }

  @PutMapping("/dishes/{dishId}/ratings")
  public ResponseEntity<Void> updateDishRating(
          @PathVariable UUID dishId,
          @Valid @RequestBody RatingUpdateRequest requestBody
  ) {
    dishService.updateDishRating(dishId, requestBody);
    return ResponseEntity.noContent().build();
  }
}
