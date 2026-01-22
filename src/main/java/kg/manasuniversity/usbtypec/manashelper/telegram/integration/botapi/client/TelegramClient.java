package kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.client;

import kg.manasuniversity.usbtypec.manashelper.telegram.exception.TelegramClientException;
import kg.manasuniversity.usbtypec.manashelper.telegram.exception.TelegramServerException;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model.TelegramSendMessageRequest;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model.TelegramSendMessageResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

import java.time.Duration;

@Service
public class TelegramClient {

  private final WebClient webClient;

  public TelegramClient(@Value("${telegram.bot.token}") String botToken) {
    webClient = WebClient.create("https://api.telegram.org/bot" + botToken);
  }

  public TelegramSendMessageResponse sendMessage(long chatId, String text) throws  TelegramClientException, TelegramServerException {
    return webClient.post()
            .uri("/sendMessage")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(new TelegramSendMessageRequest(chatId, text, "html"))
            .retrieve()
            .onStatus(HttpStatusCode::is4xxClientError, response -> response.bodyToMono(String.class).map(TelegramClientException::new))
            .onStatus(HttpStatusCode::is5xxServerError, response -> response.bodyToMono(String.class).map(TelegramServerException::new))
            .bodyToMono(TelegramSendMessageResponse.class)
            .timeout(Duration.ofSeconds(5))
            .block();
  }
}
