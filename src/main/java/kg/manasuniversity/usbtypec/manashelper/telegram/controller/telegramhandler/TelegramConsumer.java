package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.longpolling.interfaces.LongPollingUpdateConsumer;
import org.telegram.telegrambots.meta.api.objects.Update;

import java.util.List;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

@Component
@RequiredArgsConstructor
@Slf4j
public class TelegramConsumer implements LongPollingUpdateConsumer {

    private final List<TelegramUpdateHandler> handlers;

    private final ExecutorService executor = new ThreadPoolExecutor(
        4,
        8,
        60L,
        TimeUnit.SECONDS,
        new ArrayBlockingQueue<>(200),
        new ThreadPoolExecutor.CallerRunsPolicy()
    );

    @Override
    public void consume(List<Update> updates) {
        for (Update update : updates) {
            executor.submit(() -> process(update));
        }
    }

    private void process(Update update) {
        for (TelegramUpdateHandler handler : handlers) {
            if (handler.shouldHandle(update)) {
                try {
                    handler.handle(update);
                } catch (Exception e) {
                    log.error("Handler failed", e);
                }
                return;
            }
        }
    }
}
