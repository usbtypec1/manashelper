package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import jakarta.annotation.PreDestroy;
import kg.usbtypec.telegramfsm.core.engine.FlowEngine;
import kg.usbtypec.telegramfsm.core.exception.FlowExecutionException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.longpolling.interfaces.LongPollingUpdateConsumer;
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
public class TelegramConsumer implements LongPollingUpdateConsumer {
    private final FlowEngine flowEngine;
    private final List<TelegramUpdateHandler> handlers;

    private final ExecutorService executor = Executors.newVirtualThreadPerTaskExecutor();
    private final Map<Long, CompletableFuture<Void>> chatProcessingQueues = new ConcurrentHashMap<>();

    /**
     * The library's default {@code consume(List)} funnels every update, for every chat, through a single
     * shared background thread. Since handlers make blocking calls (OBIS login/scrape, RestClient calls),
     * one slow chat would stall every other chat. Instead, dispatch each update onto its own virtual thread,
     * chained per chat id so a single chat's updates still process in order, while different chats run
     * concurrently. Each chat's queue entry is dropped once its chain drains, so
     * {@code chatProcessingQueues} doesn't grow unbounded as new chats come and go.
     */
    @Override
    public void consume(List<Update> updates) {
        updates.forEach(this::dispatch);
    }

    private void dispatch(Update update) {
        Long chatId;
        if (update.hasMessage()) {
            chatId = update.getMessage().getChatId();
        } else if (update.hasCallbackQuery()) {
            chatId = update.getCallbackQuery().getMessage().getChatId();
        } else {
            chatId = null;
        }

        if (chatId == null) {
            executor.execute(() -> handleUpdate(update));
            return;
        }

        chatProcessingQueues.compute(chatId, (id, previousTask) -> {
            CompletableFuture<Void> previous = previousTask != null
                ? previousTask
                : CompletableFuture.completedFuture(null);
            CompletableFuture<Void> chained = previous
                .thenRunAsync(() -> handleUpdate(update), executor)
                .exceptionally(e -> {
                    log.error("Unhandled error processing Telegram update for chat {}", id, e);
                    return null;
                });
            chained.whenComplete((result, error) -> chatProcessingQueues.remove(id, chained));
            return chained;
        });
    }

    private void handleUpdate(Update update) {
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
        executor.close();
    }
}
