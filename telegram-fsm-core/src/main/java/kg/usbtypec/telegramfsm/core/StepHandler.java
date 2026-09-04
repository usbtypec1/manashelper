package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

/**
 * One (filter, handler) entry attached to a {@link FlowStep}. A step can hold any number of these, of any
 * kind, in any order - built with {@link FlowBuilder#or(StepHandler)}. When a step is reached, its handlers
 * are tried in the order they were added and the first whose filter matches the incoming update runs.
 */
public sealed interface StepHandler permits MessageStepHandler, CallbackQueryStepHandler {

    boolean matches(Update update, FlowContext context);

    void invoke(Update update, FlowContext context) throws TelegramApiException;
}
