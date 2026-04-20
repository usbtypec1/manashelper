package kg.manasuniversity.usbtypec.manashelper.timetable.service.manas;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.CourseTimetable;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.manas.client.TimetableClient;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.manas.parser.TimetableParser;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TimetableFetchService {
    private final TimetableClient timetableClient;
    private final TimetableParser timetableParser;

    public List<CourseTimetable> fetchTimetable(Course course) {
        String html = timetableClient.fetchTimetableHtml(course.getId());
        return timetableParser.parse(course.getId(), html);
    }
}
