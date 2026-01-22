package kg.manasuniversity.usbtypec.manashelper.user.dto.response;

public record UserGetResponse(
        long id,
        String fullName,
        String username,
        boolean isTimetableChangeNotificationsEnabled,
        boolean isNoonFoodMenuNotificationsEnabled,
        boolean isEveningFoodMenuNotificationsEnabled
) {
}
