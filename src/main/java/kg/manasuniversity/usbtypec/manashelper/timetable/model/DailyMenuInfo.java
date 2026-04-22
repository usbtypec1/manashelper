package kg.manasuniversity.usbtypec.manashelper.timetable.model;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public record DailyMenuInfo(
    UUID id,
    List<Dish> dishes,
    LocalDate date,
    double averageRatingScore,
    int ratingsCount,
    int viewsCount,
    int viewsCountForLastHour
) {
}
