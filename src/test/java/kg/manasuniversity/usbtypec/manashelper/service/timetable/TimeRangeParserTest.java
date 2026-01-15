package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import org.junit.jupiter.api.Test;

import java.time.LocalTime;

import static org.assertj.core.api.Assertions.assertThat;

class TimeRangeParserTest {

  @Test
  void parsesTimeRangeWithWhitespace() {
    TimeRange range = TimeRangeParser.parse(" 08:30 - 10:05 ");

    assertThat(range.startsAt()).isEqualTo(LocalTime.of(8, 30));
    assertThat(range.endsAt()).isEqualTo(LocalTime.of(10, 5));
  }
}
