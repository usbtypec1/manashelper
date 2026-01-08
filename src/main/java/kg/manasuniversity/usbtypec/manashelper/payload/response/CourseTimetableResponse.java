package kg.manasuniversity.usbtypec.manashelper.payload.response;

import kg.manasuniversity.usbtypec.manashelper.model.PeriodTimetable;

import java.util.List;

public record CourseTimetableResponse(
        int courseId,
        String courseName,
        List<PeriodTimetable> timetable
) {
}
