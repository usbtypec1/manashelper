package kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model;

import jakarta.annotation.Nullable;
import jakarta.validation.constraints.NotNull;

public record LessonAttendance(
        @NotNull String lessonName,
        @NotNull String lessonCode,
        @Nullable Double theorySkipsPercentage,
        @Nullable Double practiceSkipsPercentage
) {
}
