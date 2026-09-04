package kg.usbtypec.telegramfsm.sample;

import kg.usbtypec.telegramfsm.core.CallbackQueryHandler;
import kg.usbtypec.telegramfsm.core.FlowContext;
import kg.usbtypec.telegramfsm.core.callback.CallbackData;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.AnswerCallbackQuery;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class TopUpCancelHandler implements CallbackQueryHandler {

    private final TelegramClient telegramClient;

    public TopUpCancelHandler(TelegramClient telegramClient) {
        this.telegramClient = telegramClient;
    }

    @Override
    public boolean matches(CallbackQuery callbackQuery, FlowContext context) {
        return CallbackData.parse(callbackQuery).hasPrefix("cancel");
    }

    @Override
    public void handle(CallbackQuery callbackQuery, FlowContext context) throws TelegramApiException {
        long chatId = callbackQuery.getMessage().getChatId();

        telegramClient.execute(AnswerCallbackQuery.builder()
                .callbackQueryId(callbackQuery.getId())
                .build());
        telegramClient.execute(SendMessage.builder()
                .chatId(chatId)
                .text("Top up cancelled.")
                .build());
    }
}
