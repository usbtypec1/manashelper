package kg.manasuniversity.usbtypec.manashelper.telegram.scheduler;

import kg.manasuniversity.usbtypec.manashelper.telegram.service.TelegramMessageSenderService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@Slf4j
public class TelegramMessageSenderJob {
  private final TelegramMessageSenderService telegramMessageSenderService;

  public TelegramMessageSenderJob(TelegramMessageSenderService telegramMessageSenderService) {
    this.telegramMessageSenderService = telegramMessageSenderService;
  }

  @Scheduled(fixedRate = 30_000)
  public void sendPendingMessages() {
    log.info("Sending pending Telegram messages...");
    telegramMessageSenderService.sendPendingMessages();
    log.info("Finished sending pending Telegram messages.");
  }
}
