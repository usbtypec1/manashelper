package kg.manasuniversity.usbtypec.manashelper.service;

import jakarta.annotation.Nullable;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Service
public class TelegramClient {
  private record SendMessageRequest(long chat_id, String text) {
  }

  public record ResponseData(boolean ok, @Nullable String description) {
  }

  private final WebClient webClient;

  public TelegramClient(@Value("${telegram.bot.token}") String botToken) {
    webClient = WebClient.create("https://api.telegram.org/bot" + botToken);
  }

  public ResponseData sendMessage(long chatId, String text) {
    return webClient.post()
            .uri("/sendMessage")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(new SendMessageRequest(chatId, text))
            .retrieve()
            .bodyToMono(ResponseData.class)
            .block();
  }
}
