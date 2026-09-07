package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.methods.AnswerCallbackQuery;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboard;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

/**
 * Everything a {@link CallbackQueryHandler} needs to react to one incoming button press: the callback query
 * itself, the shared {@link FlowContext} for this chat's flow, and ready-to-use replies backed by the
 * {@link TelegramClient}.
 */
public class CallbackQueryContext {

    private final Update update;
    private final TelegramClient telegramClient;
    private final FlowContext flowContext;

    public CallbackQueryContext(Update update, TelegramClient telegramClient, FlowContext flowContext) {
        this.update = update;
        this.telegramClient = telegramClient;
        this.flowContext = flowContext;
    }

    public CallbackQuery getCallbackQuery() {
        return update.getCallbackQuery();
    }

    public String getCallbackData() {
        return getCallbackQuery().getData();
    }

    public long getChatId() {
        return UpdateUtils.getChatId(update);
    }

    public FlowContext getFlowContext() {
        return flowContext;
    }

    public void answerMessage(String text) throws TelegramApiException {
        answerMessage(text, null);
    }

    public void answerMessage(String text, ReplyKeyboard replyMarkup) throws TelegramApiException {
        telegramClient.execute(SendMessage.builder()
                .chatId(getChatId())
                .text(text)
                .parseMode("html")
                .replyMarkup(replyMarkup)
                .build());
    }

    public void answerAlert(String text) throws TelegramApiException {
        telegramClient.execute(AnswerCallbackQuery.builder()
                .callbackQueryId(getCallbackQuery().getId())
                .text(text)
                .showAlert(true)
                .build());
    }
}
