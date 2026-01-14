package kg.manasuniversity.usbtypec.manashelper.payload.request;

import jakarta.annotation.Nullable;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;

public record RatingUpdateRequest(
        @Min(value = 1, message = "Score must be at least 1")
        @Max(value = 5, message = "Score must be at most 5")
        int score,

        @Nullable
        @Size(max = 255, message = "Comment must be at most 255 characters long")
        String comment,

        long userId
) {
}
