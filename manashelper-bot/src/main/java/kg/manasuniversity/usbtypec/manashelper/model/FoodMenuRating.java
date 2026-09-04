package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.UUID;

public record FoodMenuRating(
    UUID dailyMenuId,
    int rating
) {
}
