package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import java.time.LocalTime;

class TimeRangeParser {
  private TimeRangeParser() {}

  static TimeRange parse(String period) {
    String[] times = period.split("-");
    LocalTime startsAt = parseTime(times[0]);
    LocalTime endsAt = parseTime(times[1]);
    return new TimeRange(startsAt, endsAt);
  }

  private static LocalTime parseTime(String time) {
    String[] parts = time.trim().split(":");
    return LocalTime.of(Integer.parseInt(parts[0]), Integer.parseInt(parts[1]));
  }
}
