package kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.client;

import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model.TelegramSendMessageRequest;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model.TelegramSendMessageResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;

@Service
public class TelegramClient {

  private final WebClient webClient;

  public TelegramClient(@Value("${telegram.bot.token}") String botToken) {
    webClient = WebClient.create("https://api.telegram.org/bot" + botToken);
  }

  public TelegramSendMessageResponse sendMessage(long chatId, String text) {
    return webClient.post()
            .uri("/sendMessage")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(new TelegramSendMessageRequest(chatId, text, "html"))
            .retrieve()
            .bodyToMono(TelegramSendMessageResponse.class)
            .block();
  }
}
