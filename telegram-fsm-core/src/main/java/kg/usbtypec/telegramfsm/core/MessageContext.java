package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboard;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

/**
 * Everything a {@link MessageHandler} needs to react to one incoming message: the message itself, the shared
 * {@link FlowContext} for this chat's flow, and ready-to-use replies backed by the {@link TelegramClient}.
 */
public class MessageContext {

    private final Update update;
    private final TelegramClient telegramClient;
    private final FlowContext flowContext;

    public MessageContext(Update update, TelegramClient telegramClient, FlowContext flowContext) {
        this.update = update;
        this.telegramClient = telegramClient;
        this.flowContext = flowContext;
    }

    public Message getMessage() {
        return update.getMessage();
    }

    public String getText() {
        return getMessage().getText();
    }

    public long getChatId() {
        return UpdateUtils.getChatId(update);
    }

    public FlowContext getFlowContext() {
        return flowContext;
    }

    public void answer(String text) throws TelegramApiException {
        answer(text, null);
    }

    public void answer(String text, ReplyKeyboard replyMarkup) throws TelegramApiException {
        telegramClient.execute(SendMessage.builder()
                .chatId(getChatId())
                .text(text)
                .parseMode("html")
                .replyMarkup(replyMarkup)
                .build());
    }
}
