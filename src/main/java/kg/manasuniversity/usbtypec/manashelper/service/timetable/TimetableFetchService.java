package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.service.TimetableClient;
import kg.manasuniversity.usbtypec.manashelper.service.TimetableParser;
import org.springframework.stereotype.Service;

@Service
public class TimetableFetchService {
  private final TimetableClient timetableClient;
  private final TimetableParser timetableParser;

  public TimetableFetchService(TimetableClient timetableClient, TimetableParser timetableParser) {
    this.timetableClient = timetableClient;
    this.timetableParser = timetableParser;
  }

  public CourseTimetableResponse fetchTimetable(Course course) {
    String html = timetableClient.fetchTimetableHtml(course.getId());
    return timetableParser.parse(course.getId(), html);
  }
}
