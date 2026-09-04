package kg.manasuniversity.usbtypec.manashelper.model;

import lombok.Builder;

@Builder
public record LessonAttendanceAndSkipsOpportunity(
    String lessonName,
    String lessonCode,
    Double theorySkipsPercentage,
    Double practiceSkipsPercentage,
    Integer theorySkippable,
    Integer practiceSkippable
) {
}
