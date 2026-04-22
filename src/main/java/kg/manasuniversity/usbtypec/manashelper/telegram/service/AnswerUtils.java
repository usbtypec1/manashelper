package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.telegram.telegrambots.meta.api.methods.AnswerCallbackQuery;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.methods.updatingmessages.EditMessageText;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboard;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateUtils.getChatId;
import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateUtils.getMessageId;

@Service
@RequiredArgsConstructor
public class AnswerUtils {
    protected final TelegramClient telegramClient;

    public void answerTextMessage(Update update, String text, ReplyKeyboard markup) throws TelegramApiException {
        SendMessage sendMessage = SendMessage.builder()
            .chatId(getChatId(update))
            .text(text)
            .replyMarkup(markup)
            .parseMode("html")
            .build();
        telegramClient.execute(sendMessage);
    }

    public void answerTextMessage(Update update, String text) throws TelegramApiException {
        answerTextMessage(update, text, null);
    }

    public void answerEmptyCallbackQuery(Update update) throws TelegramApiException {
        if (update.hasCallbackQuery()) {
            AnswerCallbackQuery answerCallbackQuery = AnswerCallbackQuery.builder()
                .callbackQueryId(update.getCallbackQuery().getId())
                .text("")
                .build();
            telegramClient.execute(answerCallbackQuery);
        }
    }

    public void editTextMessage(Update update, String text, InlineKeyboardMarkup markup)
        throws TelegramApiException {
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