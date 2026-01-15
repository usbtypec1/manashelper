package kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.dto.response;


public record DailyMenuRatingResponse(
        long userId,
        String userFullName,
        double score,
        String comment
) {
}
