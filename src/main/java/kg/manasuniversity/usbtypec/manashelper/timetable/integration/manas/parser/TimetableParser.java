package kg.manasuniversity.usbtypec.manashelper.timetable.integration.manas.parser;

import kg.manasuniversity.usbtypec.manashelper.timetable.enums.LessonType;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.Period;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.TimeRangeParser;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class TimetableParser {
  private static final Map<String, LessonType> LESSON_TYPE_MAP = Map.of(
          "#c3e6cb", LessonType.MANDATORY_MAJOR,
          "#b8daff", LessonType.MANDATORY_GENERAL,
          "#ffeeba", LessonType.ELECTIVE_MAJOR
  );

  private LessonType getLessonType(Element div) {
    String bg = div.attr("style");
    for (var entry : LESSON_TYPE_MAP.entrySet()) {
      if (bg.contains(entry.getKey())) {
        return entry.getValue();
      }
    }
    return LessonType.ELECTIVE_OTHER;
  }

  private CourseTimetableResponse.Lesson parseLessonCard(Period period, Element div, int weekday) {
    String[] parts = div.html().split("<br>");
    String name = parts.length > 0 ? parts[0].trim() : null;
    String teacherName = parts.length > 1 ? parts[1].trim() : null;
    String location = parts.length > 2 ? parts[2].trim() : null;
    LessonType lessonType = getLessonType(div);
    return new CourseTimetableResponse.Lesson(
            name,
            teacherName,
            location,
            period.startsAt(),
            period.endsAt(),
            weekday,
            lessonType
    );
  }

  private List<CourseTimetableResponse.Lesson> parseLessonsColumn(Period period, Element td, int weekday) {
    return td.select("div")
            .stream()
            .map(div -> parseLessonCard(period, div, weekday))
            .toList();
  }

  public CourseTimetableResponse parse(int courseId, String html) {
    Document doc = Jsoup.parse(html);

    Elements rows = doc.select("tr");

    List<CourseTimetableResponse.Lesson> result = new ArrayList<>();

    for (int i = 1; i < rows.size(); i++) {
      Element tr = rows.get(i);
      Elements tds = tr.select("td");

      Period period = TimeRangeParser.parse(tds.get(0).text());

      for (int weekday = 1; weekday <= 5; weekday++) {
        result.addAll(parseLessonsColumn(period, tds.get(weekday), weekday));
      }
    }
    return new CourseTimetableResponse(courseId, result);
  }
}
