package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.methods.updatingmessages.EditMessageText;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboard;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public abstract class TelegramUpdateHandler {
    protected final TelegramClient telegramClient;

    protected TelegramUpdateHandler(
        @Qualifier("telegramApiClient")
        TelegramClient telegramClient
    ) {
        this.telegramClient = telegramClient;
    }

    public abstract boolean shouldHandle(Update update);

    public abstract void handle(Update update) throws TelegramApiException;

    protected Long getChatId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getChatId();
        } else if (update.hasCallbackQuery()) {
            return update.getCallbackQuery().getMessage().getChatId();
        }
        throw new IllegalArgumentException("Unknown update type");
    }

    protected Integer getMessageId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getMessageId();
        } else if (update.hasCallbackQuery()) {
            return update.getCallbackQuery().getMessage().getMessageId();
        }
        throw new IllegalArgumentException("Unknown update type");
    }

    protected void answerTextMessage(Update update, String text, ReplyKeyboard markup) throws TelegramApiException {
        SendMessage sendMessage = SendMessage.builder()
            .chatId(getChatId(update))
            .text(text)
            .replyMarkup(markup)
            .parseMode("html")
            .build();
        telegramClient.execute(sendMessage);
    }

    protected void answerTextMessage(Update update, String text) throws TelegramApiException {
        answerTextMessage(update, text, null);
    }

    protected void editTextMessage(Update update, String text, InlineKeyboardMarkup markup
    ) throws TelegramApiException {
        EditMessageText editMessageText = EditMessageText.builder()
            .chatId(getChatId(update))
            .text(text)
            .messageId(getMessageId(update))
            .replyMarkup(markup)
            .parseMode("html")
            .build();
        telegramClient.execute(editMessageText);
    }
}
