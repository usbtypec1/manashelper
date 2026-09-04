package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

/**
 * Handles a button press (callback query) received while a {@link Flow} is waiting on the step this handler
 * is attached to. When a step has more than one handler (see {@link FlowBuilder#or}), {@link #matches}
 * decides whether this particular handler is the one that should react to the callback query.
 */
@FunctionalInterface
public interface CallbackQueryHandler {

    void handle(CallbackQuery callbackQuery, FlowContext context) throws TelegramApiException;

    /**
     * Whether this handler should react to the given callback query. Defaults to always accepting; override
     * to filter, e.g. by {@code callback_data} (see {@link kg.usbtypec.telegramfsm.core.callback.CallbackData}),
     * so several callback handlers can share one step.
     */
    default boolean matches(CallbackQuery callbackQuery, FlowContext context) {
        return true;
    }
}
