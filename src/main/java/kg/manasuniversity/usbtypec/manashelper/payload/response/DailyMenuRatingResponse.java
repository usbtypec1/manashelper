package kg.manasuniversity.usbtypec.manashelper.payload.response;


public record DailyMenuRatingResponse(
        long userId,
        String userFullName,
        double score,
        String comment
) {
}
