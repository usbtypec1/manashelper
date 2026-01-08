package kg.manasuniversity.usbtypec.manashelper.service;

import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

@Service
public class DailyMenuClient {

  private final WebClient webClient;

  public DailyMenuClient() {
    webClient = WebClient.create("https://beslenme.manas.edu.kg/");
  }

  public String fetchDailyMenuHtml() {
    return webClient.get()
            .uri("/menu")
            .retrieve()
            .bodyToMono(String.class)
            .block();
  }
}
