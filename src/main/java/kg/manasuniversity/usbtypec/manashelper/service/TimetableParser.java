package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.Lesson;
import kg.manasuniversity.usbtypec.manashelper.model.PeriodTimetable;
import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
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

  private Lesson parseLessonCard(int courseId, Element div, int weekday) {
    String[] parts = div.html().split("<br>");
    return new Lesson(
            courseId,
            parts.length > 0 ? parts[0].trim() : null,
            parts.length > 1 ? parts[1].trim() : null,
            parts.length > 2 ? parts[2].trim() : null,
            getLessonType(div),
            weekday
    );
  }

  private List<Lesson> parseLessonsColumn(int courseId, Element td, int weekday) {
    List<Lesson> lessons = new ArrayList<>();
    for (Element div : td.select("div")) {
      lessons.add(parseLessonCard(courseId, div, weekday));
    }
    return lessons;
  }

  public CourseTimetableResponse parse(int courseId, String html) {
    Document doc = Jsoup.parse(html);

    Elements titles = doc.select("h3");
    String courseName = !titles.isEmpty() ? titles.get(0).text() : null;

    Elements rows = doc.select("tr");

    List<PeriodTimetable> result = new ArrayList<>();

    for (int i = 1; i < rows.size(); i++) {
      Element tr = rows.get(i);
      Elements tds = tr.select("td");

      result.add(new PeriodTimetable(
              tds.get(0).text(),
              parseLessonsColumn(courseId, tds.get(1), 1),
              parseLessonsColumn(courseId, tds.get(2), 2),
              parseLessonsColumn(courseId, tds.get(3), 3),
              parseLessonsColumn(courseId, tds.get(4), 4),
              parseLessonsColumn(courseId, tds.get(5), 5)
      ));
    }
    return new CourseTimetableResponse(
            courseId,
            courseName,
            result
    );
  }
}
