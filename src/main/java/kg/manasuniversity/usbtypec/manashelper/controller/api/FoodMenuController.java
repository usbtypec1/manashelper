package kg.manasuniversity.usbtypec.manashelper.controller.api;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.service.DailyMenuService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/food-menu")
public class FoodMenuController {
  private final DailyMenuService dailyMenuService;

  public FoodMenuController(DailyMenuService dailyMenuService) {
    this.dailyMenuService = dailyMenuService;
  }

  @GetMapping
  public List<DailyMenu> getDailyMenuList() {
    return dailyMenuService.getLastDailyMenus();
  }
}
