package kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model;

import jakarta.annotation.Nullable;
import jakarta.validation.constraints.NotNull;

public record Exam(
        @NotNull String name,
        @Nullable String score
) {
}
