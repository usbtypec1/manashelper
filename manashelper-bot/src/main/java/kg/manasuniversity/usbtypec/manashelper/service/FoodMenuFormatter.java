package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenuModel;
import kg.manasuniversity.usbtypec.manashelper.model.DishModel;
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

    public String format(DailyMenuModel dailyMenuModel) {
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append("🍽️ Меню на ")
            .append(dailyMenuModel.date())
            .append(" (")
            .append(dailyMenuModel.date().format(DATE_TIME_FORMATTER))
            .append(") 🍽️\n\n");

        for (DishModel dishModel : dailyMenuModel.dishModels()) {
            stringBuilder.append("🧂 <u>")
                .append(dishModel.name())
                .append("</u>\n🌱 Калории: ")
                .append(dishModel.calories())
                .append("\n\n");
        }

        int totalCalories = dailyMenuModel.dishModels().stream().mapToInt(DishModel::calories).sum();
        stringBuilder
            .append("🔥 Сумма калорий: ")
            .append(totalCalories)
            .append("\n")
            .append("Сегодняшняя средняя оценка: ")
            .append(dailyMenuModel.averageRatingScore())
            .append(" (")
            .append(dailyMenuModel.ratingsCount())
            .append(" оценок)")
            .append("\n")
            .append("👀 Просмотров: ")
            .append(dailyMenuModel.viewsCount());

        return stringBuilder.toString();
    }

    public List<InputMediaPhoto> buildPhotos(String text, DailyMenuModel dailyMenuModel) {
        List<InputMediaPhoto> photos = new ArrayList<>(dailyMenuModel.dishModels().size());
        photos.add(
            InputMediaPhoto.builder()
                .media(dailyMenuModel.dishModels().get(0).photoUrl())
                .caption(text)
                .parseMode("html")
                .build()
        );

        List<InputMediaPhoto> restPhotos = dailyMenuModel.dishModels().subList(1, dailyMenuModel.dishModels().size())
            .stream()
            .map(dish -> new InputMediaPhoto(dish.photoUrl()))
            .toList();
        photos.addAll(restPhotos);
        return photos;
    }
}
