package kg.manasuniversity.usbtypec.manashelper.parser;

import kg.manasuniversity.usbtypec.manashelper.model.Period;
import lombok.experimental.UtilityClass;

import java.time.LocalTime;

@UtilityClass
public class TimeRangeParser {

    public Period parse(String period) {
        String[] times = period.split("-");
        LocalTime startsAt = parseTime(times[0]);
        LocalTime endsAt = parseTime(times[1]);
        return new Period(startsAt, endsAt);
    }

    private LocalTime parseTime(String time) {
        String[] parts = time.trim().split(":");
        return LocalTime.of(Integer.parseInt(parts[0]), Integer.parseInt(parts[1]));
    }
}
