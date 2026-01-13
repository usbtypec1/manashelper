package kg.manasuniversity.usbtypec.manashelper.scheduledtasks;

import kg.manasuniversity.usbtypec.manashelper.service.TelegramMessageService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class PendingTelegramMessagesSendTask {
  private static final Logger log = LoggerFactory.getLogger(PendingTelegramMessagesSendTask.class);

  private final TelegramMessageService telegramMessageService;

  public PendingTelegramMessagesSendTask(TelegramMessageService telegramMessageService) {
    this.telegramMessageService = telegramMessageService;
  }

  @Scheduled(fixedRate = 30_000)
  public void sendPendingMessages() {
    log.info("Sending pending Telegram messages...");
    telegramMessageService.sendPendingMessages();
    log.info("Finished sending pending Telegram messages.");
  }
}
