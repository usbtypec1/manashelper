package kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.controller.api;

import jakarta.validation.Valid;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.dto.request.DailyMenuRatingUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dish.dto.request.DishRatingUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.dto.response.DailyMenuRatingResponse;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.service.DailyMenuService;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.service.DishService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;
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

  @GetMapping("/{dailyMenuId}/ratings")
  public ResponseEntity<List<DailyMenuRatingResponse>> getDailyMenuRating(
          @PathVariable UUID dailyMenuId,
          @RequestParam(name = "userId", required = false) Long userId
  ) {
    List<DailyMenuRatingResponse> rating = dailyMenuService.getDailyMenuRatings(dailyMenuId, userId);
    return ResponseEntity.ok(rating);
  }

  @PutMapping("/{dailyMenuId}/ratings")
  public ResponseEntity<Void> updateDailyMenuRating(
          @PathVariable UUID dailyMenuId,
          @Valid @RequestBody DailyMenuRatingUpdateRequest requestBody
  ) {
    dailyMenuService.updateDailyMenuRating(dailyMenuId, requestBody);
    return ResponseEntity.noContent().build();
  }

  @PutMapping("/dishes/{dishId}/ratings")
  public ResponseEntity<Void> updateDishRating(
          @PathVariable UUID dishId,
          @Valid @RequestBody DishRatingUpdateRequest requestBody
  ) {
    dishService.updateDishRating(dishId, requestBody);
    return ResponseEntity.noContent().build();
  }
}
