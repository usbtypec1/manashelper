package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.model.FoodMenuRating;

import java.util.Optional;
import java.util.UUID;

public class FoodMenuRatingCallbackDataFilter {

    public static Optional<FoodMenuRating> parse(String callbackData) {
        String[] parts = callbackData.split(":");
        if (parts.length != 3) {
            return Optional.empty();
        }
        if (!"food_menu_rating".equals(parts[0])) {
            return Optional.empty();
        }
        try {
            UUID dailyMenuId = UUID.fromString(parts[1]);
            int rating = Integer.parseInt(parts[2]);
            return Optional.of(new FoodMenuRating(dailyMenuId, rating));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    public static String pack(UUID dailyMenu, int rating) {
        return "food_menu_rating:" + dailyMenu + ":" + rating;
    }
}
