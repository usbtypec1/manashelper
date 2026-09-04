package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

public record MessageStepHandler(MessageHandler handler) implements StepHandler {

    @Override
    public boolean matches(Update update, FlowContext context) {
        return update.hasMessage() && handler.matches(update.getMessage(), context);
    }

    @Override
    public void invoke(Update update, FlowContext context) throws TelegramApiException {
        handler.handle(update.getMessage(), context);
    }
}
