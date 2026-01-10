package kg.manasuniversity.usbtypec.manashelper.model;

import jakarta.annotation.Nullable;
import jakarta.validation.constraints.NotNull;

public record Exam(
        @NotNull String name,
        @Nullable String score
) {
}
