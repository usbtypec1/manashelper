package kg.manasuniversity.usbtypec.manashelper.client;

import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

@Service
public class DailyMenuClient {
    private static final String DAILY_MENU_BASE_URL = "https://beslenme.manas.edu.kg";
    private static final String DAILY_MENU_URL = "/menu";

    private final RestClient restClient = RestClient.create(DAILY_MENU_BASE_URL);

    public String fetchDailyMenuHtml() {
        return restClient.get()
            .uri(DAILY_MENU_URL)
            .retrieve()
            .body(String.class);
    }
}
