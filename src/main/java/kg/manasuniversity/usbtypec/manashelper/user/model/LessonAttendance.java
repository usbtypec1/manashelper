package kg.manasuniversity.usbtypec.manashelper.user.model;

public record LessonAttendance(
        String lessonName,
        String lessonCode,
        Double theorySkipsPercentage,
        Double practiceSkipsPercentage
) {
}
