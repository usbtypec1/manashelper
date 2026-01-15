package kg.manasuniversity.usbtypec.manashelper.user.dto.request;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record UserUpdateCredentialsRequest(
        @NotNull
        @Size(min = 1, max = 255, message = "Student number must be between 1 and 255 characters long")
        String studentNumber,

        @NotNull
        @Size(min = 1, max = 255, message = "Password must be between 1 and 255 characters long")
        String plainPassword
) {
}
