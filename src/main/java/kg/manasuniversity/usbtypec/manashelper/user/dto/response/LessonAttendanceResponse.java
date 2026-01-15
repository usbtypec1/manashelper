package kg.manasuniversity.usbtypec.manashelper.user.dto.response;

public record LessonAttendanceResponse(
        String lessonName,
        String lessonCode,
        Double theorySkipsPercentage,
        Double practiceSkipsPercentage
) {
}
