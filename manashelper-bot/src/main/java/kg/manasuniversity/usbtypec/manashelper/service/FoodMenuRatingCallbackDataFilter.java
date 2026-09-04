package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.FoodMenuRating;
import lombok.experimental.UtilityClass;

import java.util.Optional;
import java.util.UUID;

@UtilityClass
public class FoodMenuRatingCallbackDataFilter {

    public Optional<FoodMenuRating> parse(String callbackData) {
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
        } catch (IllegalArgumentException _) {
            return Optional.empty();
        }
    }

    public String pack(UUID dailyMenu, int rating) {
        return "food_menu_rating:" + dailyMenu + ":" + rating;
    }
}
