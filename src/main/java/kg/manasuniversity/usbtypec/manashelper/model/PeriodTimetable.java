package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.List;

public record PeriodTimetable(
        String period,
        List<Lesson> monday,
        List<Lesson> tuesday,
        List<Lesson> wednesday,
        List<Lesson> thursday,
        List<Lesson> friday
) {
}
