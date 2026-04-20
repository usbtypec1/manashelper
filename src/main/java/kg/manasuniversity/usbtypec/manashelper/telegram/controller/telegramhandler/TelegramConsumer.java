package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.longpolling.util.LongPollingSingleThreadUpdateConsumer;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;

@Slf4j
@RequiredArgsConstructor
@Component
public class TelegramConsumer implements LongPollingSingleThreadUpdateConsumer {
    private final List<TelegramUpdateHandler> handlers;

    @Override
    public void consume(Update update) {
        for (TelegramUpdateHandler handler : handlers) {
            if (handler.shouldHandle(update)) {
                try {
                    handler.handle(update);
                } catch (TelegramApiException e) {
                    log.error("Error handling Telegram update", e);
                }
                break;
            }
        }
    }
}
