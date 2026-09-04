package kg.manasuniversity.usbtypec.manashelper.client;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Service
public class TimetableClient {
    private final RestClient restClient = RestClient.create("http://timetable.manas.edu.kg");

    public String fetchTimetableHtml(int courseId) {
        return restClient.get()
            .uri("/department-printer/{id}", courseId)
            .retrieve()
            .body(String.class);
    }
}
