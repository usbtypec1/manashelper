package kg.manasuniversity.usbtypec.manashelper.telegram.scheduler;

import kg.manasuniversity.usbtypec.manashelper.telegram.service.TelegramMessageSenderService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class TelegramMessageSenderJob {
  private static final Logger log = LoggerFactory.getLogger(TelegramMessageSenderJob.class);

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
