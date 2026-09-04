package kg.manasuniversity.usbtypec.manashelper.parser;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenuModel;
import kg.manasuniversity.usbtypec.manashelper.model.DishModel;
import lombok.extern.slf4j.Slf4j;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

@Service
@Slf4j
public class DailyMenuParser {
    private static final DateTimeFormatter DATE_FORMAT = DateTimeFormatter.ofPattern("dd.MM.yyyy");

    private Optional<LocalDate> parseDate(Element foodMenuDate) {
        String dateString = foodMenuDate.text().trim();
        String[] dateParts = dateString.split(" ");
        if (dateParts.length < 1) {
            log.warn("Skipping invalid food menu date HTML");
            return Optional.empty();
        }
        LocalDate date = LocalDate.parse(dateParts[0], DATE_FORMAT);
        return Optional.of(date);
    }

    private Optional<String> parsePhotoUrl(Element foodItem) {
        Element photoTag = foodItem.selectFirst("img");
        if (photoTag == null) {
            log.warn("Skipping invalid photo HTML");
            return Optional.empty();
        }
        String photoUrl = photoTag.attr("src");
        return Optional.of(photoUrl);
    }

    private Optional<String> parseFoodName(Element foodItem) {
        Element foodNameTag = foodItem.selectFirst("h5");
        if (foodNameTag == null) {
            log.warn("Skipping invalid food name HTML");
            return Optional.empty();
        }
        String foodName = foodNameTag.text().trim();
        return Optional.of(foodName);
    }

    private Optional<Integer> parseCalories(Element foodItem) {
        Element caloriesTag = foodItem.selectFirst("h6");
        if (caloriesTag == null) {
            log.warn("Skipping invalid calories HTML");
            return Optional.empty();
        }
        String[] caloriesText = caloriesTag.text().trim().split(" ");
        if (caloriesText.length < 2) {
            log.warn("Skipping invalid calories HTML");
            return Optional.empty();
        }
        try {
            int caloriesCount = Integer.parseInt(caloriesText[1]);
            return Optional.of(caloriesCount);
        } catch (NumberFormatException _) {
            log.warn("Skipping food menu item with invalid calories");
            return Optional.empty();
        }
    }

    private Optional<DishModel> parseDish(Element foodItem) {
        Optional<String> photoUrl = parsePhotoUrl(foodItem);
        Optional<String> foodName = parseFoodName(foodItem);
        Optional<Integer> calories = parseCalories(foodItem);

        if (photoUrl.isEmpty() || foodName.isEmpty() || calories.isEmpty()) {
            return Optional.empty();
        }

        DishModel dishModel = new DishModel(foodName.get(), calories.get(), photoUrl.get(), null);
        return Optional.of(dishModel);
    }

    private Optional<DailyMenuModel> parseDailyFoodMenuHtml(
        Element foodMenuDate,
        Element foodMenuItems
    ) {
        Optional<LocalDate> date = parseDate(foodMenuDate);
        if (date.isEmpty()) {
            log.warn("Skipping invalid food menu date HTML");
            return Optional.empty();
        }

        Elements foodItems = foodMenuItems.select("div.item");
        List<DishModel> parsedFoodItems = new ArrayList<>();
        for (Element foodItem : foodItems) {
            Optional<DishModel> dish = parseDish(foodItem);
            dish.ifPresent(parsedFoodItems::add);
        }

        DailyMenuModel menu = new DailyMenuModel(null, parsedFoodItems, date.get(), 0.0, 0, 0);
        return Optional.of(menu);
    }

    public List<DailyMenuModel> parse(String html) {
        Document soup = Jsoup.parse(html);

        Element container = soup.select("div.container").get(1);

        List<Element> titles = container.select("div.mbr-section-head")
            .subList(1, container.select("div.mbr-section-head").size());

        Elements bodies = container.select("div.row.mt-2");

        List<DailyMenuModel> result = new ArrayList<>();

        int count = Math.min(titles.size(), bodies.size());
        for (int i = 0; i < count; i++) {
            Optional<DailyMenuModel> dailyMenu = parseDailyFoodMenuHtml(
                titles.get(i),
                bodies.get(i)
            );
            dailyMenu.ifPresent(result::add);
        }

        return result;
    }

}
