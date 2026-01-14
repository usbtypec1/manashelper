package kg.manasuniversity.usbtypec.manashelper.service.food_menu;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.model.Dish;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Service
public class DailyMenuParser {
  private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("dd.MM.yyyy");

  private DailyMenu parseDailyFoodMenuHtml(
          Element foodMenuDate,
          Element foodMenuItems
  ) {

    LocalDate date = LocalDate.parse(
            foodMenuDate.text().trim().split(" ")[0],
            DATE_FORMAT
    );

    Elements foodItems = foodMenuItems.select("div.item");
    List<Dish> parsedFoodItems = new ArrayList<>();

    for (Element foodItem : foodItems) {

      String photoUrl = foodItem.selectFirst("img").attr("src");
      String foodName = foodItem.selectFirst("h5").text().trim();

      int caloriesCount = Integer.parseInt(
              foodItem.selectFirst("h6")
                      .text()
                      .trim()
                      .split(" ")[1]
      );

      Dish dish = new Dish(foodName, caloriesCount,photoUrl);
      parsedFoodItems.add(dish);
    }

    return new DailyMenu(null, parsedFoodItems, date, 0.0, 0);
  }

  public List<DailyMenu> parse(String html) {
    Document soup = Jsoup.parse(html);

    Element container = soup.select("div.container").get(1);

    List<Element> titles = container.select("div.mbr-section-head").subList(1, container.select("div.mbr-section-head").size());

    Elements bodies = container.select("div.row.mt-2");

    List<DailyMenu> result = new ArrayList<>();

    int count = Math.min(titles.size(), bodies.size());
    for (int i = 0; i < count; i++) {
      result.add(parseDailyFoodMenuHtml(
              titles.get(i),
              bodies.get(i)
      ));
    }

    return result;
  }

}
