package kg.manasuniversity.usbtypec.manashelper.foodmenu.model;

import java.util.UUID;

public record FoodMenuRating(
    UUID dailyMenuId,
    int rating
) {
}
