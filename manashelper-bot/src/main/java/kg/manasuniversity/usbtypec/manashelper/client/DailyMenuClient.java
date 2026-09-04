package kg.manasuniversity.usbtypec.manashelper.client;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Service
public class DailyMenuClient {
    private final RestClient restClient = RestClient.create("https://beslenme.manas.edu.kg/");

    public String fetchDailyMenuHtml() {
        return restClient.get()
            .uri("/menu")
            .retrieve()
            .body(String.class);
    }
}
