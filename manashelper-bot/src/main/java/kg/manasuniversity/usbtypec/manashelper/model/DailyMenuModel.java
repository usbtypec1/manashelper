package kg.manasuniversity.usbtypec.manashelper.model;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public record DailyMenuModel(
    UUID id,
    List<DishModel> dishModels,
    LocalDate date,
    double averageRatingScore,
    int ratingsCount,
    int viewsCount
) {
}
