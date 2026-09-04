package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.model.LessonAttendance;

import java.util.ArrayList;
import java.util.List;

public class AttendanceFormatter {
    private static final int THEORY_SKIPS_THRESHOLD = 30;
    private static final int PRACTICE_SKIPS_THRESHOLD = 20;
    private static final double SKIP_PERCENTAGE_PER_LESSON = 6.25;

    public static String inflectWordSkips(int count) {
        count = Math.abs(count);
        if (count % 10 == 1 && count % 100 != 11) {
            return "пропуск";
        } else if ((count % 10 == 2 || count % 10 == 3 || count % 10 == 4)
            && (count % 100 < 12 || count % 100 > 14)) {
            return "пропуска";
        }
        return "пропусков";
    }

    public static String formatFloat(Double value) {
        if (value == null) return "-";
        String s = String.valueOf(value);
        s = s.replaceAll("0+$", "");
        s = s.replaceAll("\\.$", "");
        return s;
    }

    public static String formatAttendance(List<LessonAttendanceAndSkipsOpportunity> lessonsAttendance) {
        if (lessonsAttendance == null || lessonsAttendance.isEmpty()) {
            return "У вас нет предметов.";
        }

        List<String> lines = new ArrayList<>();

        for (LessonAttendanceAndSkipsOpportunity la : lessonsAttendance) {
            int theorySkips = la.theorySkippable();
            int practiceSkips = la.practiceSkippable();

            String lessonName = "<b>" + la.lessonName() + "</b>";

            if (practiceSkips == 0 || theorySkips == 0) {
                lessonName = "❗ " + lessonName;
            } else if (practiceSkips <= 1 || theorySkips <= 1) {
                lessonName = "⚠️ " + lessonName;
            }

            String line = lessonName + "\n"
                + "Теория: " + formatFloat(la.theorySkipsPercentage())
                + "% (осталось " + theorySkips + " " + inflectWordSkips(theorySkips) + ")\n"
                + "Практика: " + formatFloat(la.practiceSkipsPercentage())
                + "% (осталось " + practiceSkips + " " + inflectWordSkips(practiceSkips) + ")";

            lines.add(line);
        }

        return String.join("\n\n", lines);
    }

    public static LessonAttendanceAndSkipsOpportunity computeLessonSkipOpportunities(
        LessonAttendance lesson
    ) {
        Integer theorySkippable = null;
        if (lesson.theorySkipsPercentage() != null) {
            double diff = THEORY_SKIPS_THRESHOLD - lesson.theorySkipsPercentage();
            theorySkippable = (diff == SKIP_PERCENTAGE_PER_LESSON)
                ? 0
                : (int) (diff / SKIP_PERCENTAGE_PER_LESSON);
        }

        Integer practiceSkippable = null;
        if (lesson.practiceSkipsPercentage() != null) {
            double diff = PRACTICE_SKIPS_THRESHOLD - lesson.practiceSkipsPercentage();
            practiceSkippable = (diff == SKIP_PERCENTAGE_PER_LESSON)
                ? 0
                : (int) (diff / SKIP_PERCENTAGE_PER_LESSON);
        }

        return new LessonAttendanceAndSkipsOpportunity(
            lesson.lessonName(),
            lesson.lessonCode(),
            lesson.theorySkipsPercentage(),
            lesson.practiceSkipsPercentage(),
            theorySkippable,
            practiceSkippable
        );
    }


    public record LessonAttendanceAndSkipsOpportunity(
        String lessonName,
        String lessonCode,
        Double theorySkipsPercentage,
        Double practiceSkipsPercentage,
        Integer theorySkippable,
        Integer practiceSkippable
    ) {
    }
}