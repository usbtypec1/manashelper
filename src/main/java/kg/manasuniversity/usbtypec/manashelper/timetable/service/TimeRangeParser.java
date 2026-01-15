package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.model.Period;

import java.time.LocalTime;

public class TimeRangeParser {
  private TimeRangeParser() {}

  public static Period parse(String period) {
    String[] times = period.split("-");
    LocalTime startsAt = parseTime(times[0]);
    LocalTime endsAt = parseTime(times[1]);
    return new Period(startsAt, endsAt);
  }

  private static LocalTime parseTime(String time) {
    String[] parts = time.trim().split(":");
    return LocalTime.of(Integer.parseInt(parts[0]), Integer.parseInt(parts[1]));
  }
}
