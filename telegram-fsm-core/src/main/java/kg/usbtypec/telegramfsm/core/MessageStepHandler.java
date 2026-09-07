package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

public record MessageStepHandler(MessageHandler handler) implements StepHandler {

    @Override
    public boolean matches(Update update, FlowContext context, TelegramClient telegramClient) {
        return update.hasMessage() && handler.matches(new MessageContext(update, telegramClient, context));
    }

    @Override
    public void invoke(Update update, FlowContext context, TelegramClient telegramClient) throws TelegramApiException {
        handler.handle(new MessageContext(update, telegramClient, context));
    }
}
