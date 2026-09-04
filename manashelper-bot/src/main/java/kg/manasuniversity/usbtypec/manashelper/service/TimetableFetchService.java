package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.model.CourseTimetable;
import kg.manasuniversity.usbtypec.manashelper.client.TimetableClient;
import kg.manasuniversity.usbtypec.manashelper.parser.TimetableParser;
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
