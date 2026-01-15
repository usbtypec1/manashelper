package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import kg.manasuniversity.usbtypec.manashelper.telegram.entity.TelegramMessage;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model.TelegramSendMessageResponse;
import kg.manasuniversity.usbtypec.manashelper.telegram.repository.TelegramMessageRepository;
import kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.client.TelegramClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class TelegramMessageSenderService {
  private final Logger log = LoggerFactory.getLogger(TelegramMessageSenderService.class);

  private final TelegramClient telegramClient;
  private final TelegramMessageRepository telegramMessageRepository;

  public TelegramMessageSenderService(TelegramClient telegramClient, TelegramMessageRepository telegramMessageRepository) {
    this.telegramClient = telegramClient;
    this.telegramMessageRepository = telegramMessageRepository;
  }

  public void sendPendingMessages() {
    List<TelegramMessage> messages = telegramMessageRepository.findBySentAtNullAndRetriesCountGreaterThanOrderByPriorityDesc(0);
    for (TelegramMessage message : messages) {
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
      telegramMessageRepository.save(message);
    }
  }
}
