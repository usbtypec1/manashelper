package kg.manasuniversity.usbtypec.manashelper.controller.api;

import kg.manasuniversity.usbtypec.manashelper.payload.response.CourseTimetableResponse;
import kg.manasuniversity.usbtypec.manashelper.service.TimetableClient;
import kg.manasuniversity.usbtypec.manashelper.service.TimetableParser;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/timetable")
public class TimetableController {

  private final TimetableClient client;
  private final TimetableParser parser;

  public TimetableController(TimetableClient client, TimetableParser parser) {
    this.client = client;
    this.parser = parser;
  }

  @GetMapping("/course/{id}")
  public CourseTimetableResponse getTimetable(
          @PathVariable int id
  ) {
    return parser.parse(id, client.fetchTimetableHtml(id));
  }
}
