package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import kg.manasuniversity.usbtypec.manashelper.telegram.entity.TelegramMessage;
import kg.manasuniversity.usbtypec.manashelper.telegram.exception.TelegramClientException;
import kg.manasuniversity.usbtypec.manashelper.telegram.exception.TelegramServerException;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model.TelegramSendMessageResponse;
import kg.manasuniversity.usbtypec.manashelper.telegram.repository.TelegramMessageRepository;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.client.TelegramClient;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.LocalDateTime;
import java.util.List;

@Service
@Slf4j
public class TelegramMessageSenderService {

  private final TelegramClient telegramClient;
  private final TelegramMessageRepository telegramMessageRepository;

  public TelegramMessageSenderService(TelegramClient telegramClient, TelegramMessageRepository telegramMessageRepository) {
    this.telegramClient = telegramClient;
    this.telegramMessageRepository = telegramMessageRepository;
  }

  public void sendPendingMessages() {
    List<TelegramMessage> messages = telegramMessageRepository.findBySentAtNullAndRetriesCountGreaterThanOrderByPriorityDesc(0);
    for (TelegramMessage message : messages) {
      try {
        TelegramSendMessageResponse responseData = telegramClient.sendMessage(message.getChatId(), message.getText());
        if (responseData.ok()) {
          log.info("Telegram message sent successfully to chatId {}", message.getChatId());
          message.setSentAt(LocalDateTime.now());
        } else {
          message.setErrorText(responseData.description());
          message.setRetriesCount(message.getRetriesCount() - 1);
          log.warn("Failed to send Telegram message to chatId {}: {}. Retries left: {}",
                  message.getChatId(), responseData.description(), message.getRetriesCount());
        }
      } catch (TelegramServerException | TelegramClientException | WebClientRequestException | WebClientResponseException e) {
        message.setErrorText(e.getMessage());
        message.setRetriesCount(message.getRetriesCount() - 1);
        log.warn("Failed to send Telegram message to chatId {}: {}. Retries left: {}",
                message.getChatId(), e.getMessage(), message.getRetriesCount());
      }
      telegramMessageRepository.save(message);
    }
  }
}
