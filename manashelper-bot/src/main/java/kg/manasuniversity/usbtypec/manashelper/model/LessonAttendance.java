package kg.manasuniversity.usbtypec.manashelper.model;

public record LessonAttendance(
        String lessonName,
        String lessonCode,
        Double theorySkipsPercentage,
        Double practiceSkipsPercentage
) {
}
