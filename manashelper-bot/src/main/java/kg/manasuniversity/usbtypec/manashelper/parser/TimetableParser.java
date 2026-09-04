package kg.manasuniversity.usbtypec.manashelper.parser;

import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;
import kg.manasuniversity.usbtypec.manashelper.model.Period;
import kg.manasuniversity.usbtypec.manashelper.model.CourseTimetable;
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

    private CourseTimetable parseLessonCard(int courseId, Period period, Element div, int weekday) {
        String[] parts = div.html().split("<br>");
        String name = parts.length > 0 ? parts[0].trim() : null;
        String teacherName = parts.length > 1 ? parts[1].trim() : null;
        String location = parts.length > 2 ? parts[2].trim() : null;
        LessonType lessonType = getLessonType(div);
        return new CourseTimetable(
            courseId,
            name,
            teacherName,
            location,
            period.startsAt(),
            period.endsAt(),
            weekday,
            lessonType
        );
    }

    private List<CourseTimetable> parseLessonsColumn(int courseId, Period period, Element td, int weekday) {
        return td.select("div")
            .stream()
            .map(div -> parseLessonCard(courseId, period, div, weekday))
            .toList();
    }

    public List<CourseTimetable> parse(int courseId, String html) {
        Document doc = Jsoup.parse(html);

        Elements rows = doc.select("tr");

        List<CourseTimetable> result = new ArrayList<>();

        for (int i = 1; i < rows.size(); i++) {
            Element tr = rows.get(i);
            Elements tds = tr.select("td");

            Period period = TimeRangeParser.parse(tds.getFirst().text());

            for (int weekday = 1; weekday <= 5; weekday++) {
                result.addAll(parseLessonsColumn(courseId, period, tds.get(weekday), weekday));
            }
        }
        return result;
    }
}
