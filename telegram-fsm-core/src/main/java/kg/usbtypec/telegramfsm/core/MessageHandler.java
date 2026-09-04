package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

/**
 * Handles a text message received while a {@link Flow} is waiting on the step this handler is attached to.
 * When a step has more than one handler (see {@link FlowBuilder#or}), {@link #matches} decides whether this
 * particular handler is the one that should react to the message.
 */
@FunctionalInterface
public interface MessageHandler {

    void handle(Message message, FlowContext context) throws TelegramApiException;

    /**
     * Whether this handler should react to the given message. Override to
     * filter, e.g. by text content, so several message handlers can share one step.
     */
    default boolean matches(Message message, FlowContext context) {
        return false;
    }
}
