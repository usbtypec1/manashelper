package kg.manasuniversity.usbtypec.manashelper.user.service.obis.parser;

import kg.manasuniversity.usbtypec.manashelper.user.exception.ObisPageParserException;
import kg.manasuniversity.usbtypec.manashelper.user.model.Exam;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonExams;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class ObisParser {

    public List<LessonExams> parseAttendanceHtmlPage(String html) throws ObisPageParserException {
        Document doc = Jsoup.parse(html);

        Elements tableBodies = doc.select("tbody");
        if (tableBodies.isEmpty()) {
            throw new ObisPageParserException("На странице в OBIS отсутствует таблица с оценками.");
        }

        Element tbody = tableBodies.last();
        if (tbody == null) {
            throw new ObisPageParserException("На странице в OBIS отсутствует таблица с оценками.");
        }

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

    public List<LessonAttendance> parseLessonsAttendancePage(String html) throws ObisPageParserException {
        Document doc = Jsoup.parse(html);

        Element table = doc.selectFirst("table");
        if (table == null) {
            throw new ObisPageParserException("На странице в OBIS отсутствует таблица с посещаемостью.");
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

    /**
     * Retrieve CSRF token from OBIS login page HTML.
     *
     * @param html HTML content of the login page.
     * @return CSRF token as a String.
     * @throws ObisPageParserException if the CSRF token is not found.
     */
    public String parseLoginPageCsrfToken(String html) throws ObisPageParserException {
        Document doc = Jsoup.parse(html);
        Element csrfInput = doc.selectFirst("form input[name=_csrf]");
        if (csrfInput == null) {
            throw new ObisPageParserException("CSRF токен не найден на странице логина OBIS.");
        }
        String csrfToken = csrfInput.attr("value");
        if (csrfToken.isBlank()) {
            throw new ObisPageParserException("CSRF токен не найден на странице логина OBIS.");
        }
        return csrfToken;
    }

    /**
     * Get trimmed text from an Element or return null if empty.
     *
     * @param element JSoup Element.
     * @return Trimmed text or null.
     */
    private static String textOrNull(Element element) {
        String text = element.text().trim();
        return text.isEmpty() ? null : text;
    }

    /**
     * Try to parse a String to Double, return null if fails.
     *
     * @param value String value to parse.
     * @return Parsed Double or null.
     */
    private static Double tryParseDouble(String value) {
        try {
            return Double.parseDouble(value);
        } catch (Exception e) {
            return null;
        }
    }
}
