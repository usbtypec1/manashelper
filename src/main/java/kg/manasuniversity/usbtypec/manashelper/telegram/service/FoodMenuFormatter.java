package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenuInfo;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.Dish;
import org.telegram.telegrambots.meta.api.objects.media.InputMediaPhoto;

import java.time.DayOfWeek;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

public class FoodMenuFormatter {
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("dd.MM.yyyy");
    private static final ZoneId ZONE_ID = ZoneId.of("Asia/Bishkek");

    public static String formatNotFound(int skipDays) {
        ZonedDateTime now = ZonedDateTime.now(ZONE_ID);
        return "Меню на " + now.plusDays(skipDays).toLocalDate().format(DATE_TIME_FORMATTER) + " не найдено.";
    }

    public static String format(DailyMenuInfo dailyMenu) {
        StringBuilder stringBuilder = new StringBuilder();
        stringBuilder.append("🍽️ Меню на ")
            .append(dailyMenu.date().format(DATE_TIME_FORMATTER))
            .append(" (")
            .append(humanizeDayOfWeek(dailyMenu.date().getDayOfWeek()))
            .append(") 🍽️\n\n");

        for (Dish dish : dailyMenu.dishes()) {
            stringBuilder.append("🧂 <u>")
                .append(dish.name())
                .append("</u>\n🌱 Калории: ")
                .append(dish.calories())
                .append("\n\n");
        }

        int totalCalories = dailyMenu.dishes().stream().mapToInt(Dish::calories).sum();
        stringBuilder.append("🔥 Всего ").append(totalCalories).append(" калорий");

        if (dailyMenu.ratingsCount() > 0) {
            stringBuilder.append("\n")
                .append("⭐ ")
                .append(dailyMenu.averageRatingScore())
                .append(" (")
                .append(dailyMenu.ratingsCount())
                .append(" оценок)");
        }

        if (dailyMenu.viewsCount() > 0) {
            stringBuilder.append("\n👀 ").append(dailyMenu.viewsCount());

            if (dailyMenu.viewsCountForLastHour() > 0) {
                stringBuilder.append(" (")
                    .append(dailyMenu.viewsCountForLastHour())
                    .append(" за последний час)");
            }
        }

        return stringBuilder.toString();
    }

    public static List<InputMediaPhoto> buildPhotos(String text, DailyMenuInfo dailyMenu) {
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

    private static String humanizeDayOfWeek(DayOfWeek dayOfWeek) {
        return switch (dayOfWeek) {
            case MONDAY -> "понедельник";
            case TUESDAY -> "вторник";
            case WEDNESDAY -> "среда";
            case THURSDAY -> "четверг";
            case FRIDAY -> "пятница";
            case SATURDAY -> "суббота";
            case SUNDAY -> "воскресенье";
        };
    }
}
