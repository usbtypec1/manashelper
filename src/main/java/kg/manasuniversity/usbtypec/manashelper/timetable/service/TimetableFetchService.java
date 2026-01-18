package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.integration.manas.client.TimetableClient;
import kg.manasuniversity.usbtypec.manashelper.timetable.integration.manas.parser.TimetableParser;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class TimetableFetchService {
  private final TimetableClient timetableClient;
  private final TimetableParser timetableParser;

  public TimetableFetchService(TimetableClient timetableClient, TimetableParser timetableParser) {
    this.timetableClient = timetableClient;
    this.timetableParser = timetableParser;
  }

  public List<CourseTimetableResponse> fetchTimetable(Course course) {
    String html = timetableClient.fetchTimetableHtml(course.getId());
    return timetableParser.parse(course.getId(), html);
  }
}
