package kg.manasuniversity.usbtypec.manashelper.user.dto.request;

import jakarta.validation.constraints.NotNull;

public record UserUpdateRequest(
        @NotNull
        Boolean isTimetableChangeNotificationsEnabled,

        @NotNull
        Boolean isNoonFoodMenuNotificationsEnabled,

        @NotNull
        Boolean isEveningFoodMenuNotificationsEnabled
) {
}
