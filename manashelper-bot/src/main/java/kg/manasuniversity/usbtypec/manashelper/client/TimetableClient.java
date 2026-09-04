package kg.manasuniversity.usbtypec.manashelper.client;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Service
public class TimetableClient {
    private static final String TIMETABLE_BASE_URL = "http://timetable.manas.edu.kg";
    private static final String SPECIFIC_COURSE_URL = "/department-printer/{id}";

    private final RestClient restClient = RestClient.create(TIMETABLE_BASE_URL);

    public String fetchTimetableHtml(int courseId) {
        return restClient.get()
            .uri(SPECIFIC_COURSE_URL, courseId)
            .retrieve()
            .body(String.class);
    }
}
