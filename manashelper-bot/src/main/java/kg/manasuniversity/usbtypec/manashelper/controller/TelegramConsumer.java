package kg.manasuniversity.usbtypec.manashelper.controller;

import jakarta.annotation.PreDestroy;
import kg.usbtypec.telegramfsm.core.engine.FlowEngine;
import kg.usbtypec.telegramfsm.core.exception.FlowExecutionException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.longpolling.util.LongPollingSingleThreadUpdateConsumer;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Slf4j
@RequiredArgsConstructor
@Component
public class TelegramConsumer implements LongPollingSingleThreadUpdateConsumer {
    private final FlowEngine flowEngine;
    private final List<TelegramUpdateHandler> handlers;

    private final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();
    private final Map<Long, CompletableFuture<Void>> chatProcessingQueues = new ConcurrentHashMap<>();

    /**
     * The library's default {@code consume(List)} funnels every update, for every chat, through a single
     * shared background thread. Since handlers make blocking calls (OBIS login/scrape, RestClient calls),
     * one slow chat would stall every other chat. Instead, dispatch each update onto its own virtual thread,
     * chained per chat id so a single chat's updates still process in order, while different chats run
     * concurrently.
     */
    @Override
    public void consume(List<Update> updates) {
        updates.forEach(this::dispatch);
    }

    private void dispatch(Update update) {
        Long chatId = extractChatId(update);
        if (chatId == null) {
            virtualThreadExecutor.execute(() -> consume(update));
            return;
        }
        chatProcessingQueues.compute(chatId, (id, previousTask) -> {
            CompletableFuture<Void> previous = previousTask != null
                ? previousTask
                : CompletableFuture.completedFuture(null);
            return previous
                .thenRunAsync(() -> consume(update), virtualThreadExecutor)
                .exceptionally(e -> {
                    log.error("Unhandled error processing Telegram update for chat {}", id, e);
                    return null;
                });
        });
    }

    private Long extractChatId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getChatId();
        } else if (update.hasCallbackQuery()) {
            return update.getCallbackQuery().getMessage().getChatId();
        }
        return null;
    }

    @Override
    public void consume(Update update) {
        try {
            if (flowEngine.dispatch(update)) {
                return;
            }
        } catch (FlowExecutionException e) {
            log.error("Error executing flow step for Telegram update", e);
            return;
        }

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

    @PreDestroy
    void shutdown() {
        virtualThreadExecutor.close();
    }
}
