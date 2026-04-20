package kg.manasuniversity.usbtypec.manashelper.timetable.service.manas.client;

import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

@Service
public class TimetableClient {

    private final WebClient webClient;

    public TimetableClient() {
        webClient = WebClient.create("http://timetable.manas.edu.kg");
    }

    public String fetchTimetableHtml(int courseId) {
        return webClient.get()
            .uri("/department-printer/{id}", courseId)
            .retrieve()
            .bodyToMono(String.class)
            .block();
    }
}
