package kg.manasuniversity.usbtypec.manashelper.controller.api;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.service.DailyMenuClient;
import kg.manasuniversity.usbtypec.manashelper.service.DailyMenuParser;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/food-menu")
public class FoodMenuController {
  private final DailyMenuClient dailyMenuClient;
  private final DailyMenuParser dailyMenuParser;

  public FoodMenuController(DailyMenuClient dailyMenuClient, DailyMenuParser dailyMenuParser) {
    this.dailyMenuClient = dailyMenuClient;
    this.dailyMenuParser = dailyMenuParser;
  }

  @GetMapping
  public List<DailyMenu> getDailyMenuList() {
    String html = dailyMenuClient.fetchDailyMenuHtml();
    return dailyMenuParser.parse(html);
  }
}
