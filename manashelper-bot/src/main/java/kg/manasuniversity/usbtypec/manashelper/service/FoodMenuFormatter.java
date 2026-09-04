package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.model.Dish;
import lombok.experimental.UtilityClass;
import org.telegram.telegrambots.meta.api.objects.media.InputMediaPhoto;

import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@UtilityClass
public class FoodMenuFormatter {
    private final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("dd.MM.yyyy");
    private final ZoneId ZONE_ID = ZoneId.of("Asia/Bishkek");

    public String formatNotFound(int skipDays) {
        ZonedDateTime now = ZonedDateTime.now(ZONE_ID);
        return "Меню на " + now.plusDays(skipDays).toLocalDate().format(DATE_TIME_FORMATTER) + " не найдено.";
    }

    public String format(DailyMenu dailyMenu) {
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append("🍽️ Меню на ")
            .append(dailyMenu.date())
            .append(" (")
            .append(dailyMenu.date().format(DATE_TIME_FORMATTER))
            .append(") 🍽️\n\n");

        for (Dish dish : dailyMenu.dishes()) {
            stringBuilder.append("🧂 <u>")
                .append(dish.name())
                .append("</u>\n🌱 Калории: ")
                .append(dish.calories())
                .append("\n\n");
        }

        int totalCalories = dailyMenu.dishes().stream().mapToInt(Dish::calories).sum();
        stringBuilder
            .append("🔥 Сумма калорий: ")
            .append(totalCalories)
            .append("\n")
            .append("Сегодняшняя средняя оценка: ")
            .append(dailyMenu.averageRatingScore())
            .append(" (")
            .append(dailyMenu.ratingsCount())
            .append(" оценок)")
            .append("\n")
            .append("👀 Просмотров: ")
            .append(dailyMenu.viewsCount());

        return stringBuilder.toString();
    }

    public List<InputMediaPhoto> buildPhotos(String text, DailyMenu dailyMenu) {
        List<InputMediaPhoto> photos = new ArrayList<>(dailyMenu.dishes().size());
        photos.add(
            InputMediaPhoto.builder()
                .media(dailyMenu.dishes().get(0).photoUrl())
                .caption(text)
                .parseMode("html")
                .build()
        );

        List<InputMediaPhoto> restPhotos = dailyMenu.dishes().subList(1, dailyMenu.dishes().size())
            .stream()
            .map(dish -> new InputMediaPhoto(dish.photoUrl()))
            .toList();
        photos.addAll(restPhotos);
        return photos;
    }
}
