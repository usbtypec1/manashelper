package kg.manasuniversity.usbtypec.manashelper.user.dto.request;

import jakarta.annotation.Nullable;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record UserUpsertRequest(
        @NotNull
        Long id,

        @NotNull
        @Size(min = 1, max = 128, message = "Full name must be between 1 and 128 characters long")
        String fullName,

        @Nullable
        @Size(min = 1, max = 128, message = "Username must be between 1 and 128 characters long")
        String username
) {
}
