package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

public record CallbackQueryStepHandler(CallbackQueryHandler handler) implements StepHandler {

    @Override
    public boolean matches(Update update, FlowContext context) {
        return update.hasCallbackQuery() && handler.matches(update.getCallbackQuery(), context);
    }

    @Override
    public void invoke(Update update, FlowContext context) throws TelegramApiException {
        handler.handle(update.getCallbackQuery(), context);
    }
}
