package kg.manasuniversity.usbtypec.manashelper.service.obis;

import kg.manasuniversity.usbtypec.manashelper.model.Exam;
import kg.manasuniversity.usbtypec.manashelper.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.model.LessonExams;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class ObisParser {
  private static final Logger log = LoggerFactory.getLogger(ObisParser.class);

  public List<LessonExams> parseTakenGradesPage(String html) {
    Document doc = Jsoup.parse(html);

    Elements tableBodies = doc.select("tbody");
    if (tableBodies.isEmpty()) {
      return List.of();
    }

    Element tbody = tableBodies.last();
    Elements rows = tbody.select("> tr");

    List<LessonExams> lessons = new ArrayList<>();
    int i = 0;

    while (i < rows.size()) {
      Element mainRow = rows.get(i);
      Elements tds = mainRow.select("> td");

      if (tds.size() == 5) {
        String lessonCode = textOrNull(tds.get(1));
        String lessonName = textOrNull(tds.get(2));

        int rowspan = 1;
        if (tds.get(0).hasAttr("rowspan")) {
          rowspan = Integer.parseInt(tds.get(0).attr("rowspan"));
        }

        List<Exam> exams = new ArrayList<>();

        exams.add(new Exam(
                textOrNull(tds.get(3)),
                textOrNull(tds.get(4))
        ));

        for (int j = 1; j < rowspan && i + j < rows.size(); j++) {
          Element nextRow = rows.get(i + j);
          Elements nextTds = nextRow.select("> td");

          if (nextTds.size() == 2) {
            exams.add(new Exam(
                    textOrNull(nextTds.get(0)),
                    textOrNull(nextTds.get(1))
            ));
          }
        }

        lessons.add(new LessonExams(
                lessonName,
                lessonCode,
                exams
        ));

        i += rowspan;
      } else {
        i++;
      }
    }

    return lessons;
  }

  public List<LessonAttendance> parseLessonsAttendancePage(String html) {
    Document doc = Jsoup.parse(html);

    Element table = doc.selectFirst("table");
    if (table == null) {
      log.warn("No attendance table found in the HTML page");
      return List.of();
    }

    Elements rows = table.select("tr");
    List<LessonAttendance> lessons = new ArrayList<>();

    for (int i = 1; i < rows.size(); i++) { // skip header
      Element row = rows.get(i);
      Elements tds = row.select("td");

      if (tds.size() != 9) {
        continue;
      }

      String lessonCode = tds.get(1).text().trim();
      String lessonName = tds.get(2).text().trim();

      String theoryPercentage = tds.get(4).text().replace("%", "").trim();
      String practicePercentage = tds.get(6).text().replace("%", "").trim();

      lessons.add(new LessonAttendance(
              lessonName,
              lessonCode,
              tryParseDouble(theoryPercentage),
              tryParseDouble(practicePercentage)
      ));
    }

    return lessons;
  }

  public String parseLoginPageCsrfToken(String html) {
    Document doc = Jsoup.parse(html);
    Element csrfInput = doc.selectFirst("form input[name=_csrf]");
    if (csrfInput != null) {
      return csrfInput.attr("value");
    }
    return null;
  }

  private static String textOrNull(Element element) {
    String text = element.text().trim();
    return text.isEmpty() ? null : text;
  }

  private static Double tryParseDouble(String value) {
    try {
      return Double.parseDouble(value);
    } catch (Exception e) {
      return null;
    }
  }
}
