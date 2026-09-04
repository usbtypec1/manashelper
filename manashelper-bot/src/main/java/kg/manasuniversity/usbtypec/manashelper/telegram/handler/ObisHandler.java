package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class ObisHandler extends TelegramUpdateHandler {
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("📅 Йоклама")
                    .callbackData("obis:attendance")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("💯 Оценки")
                    .callbackData("obis:exams")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("Ввести данные от OBIS")
                    .callbackData("obis:credentials")
                    .build()
            )
        )
        .build();

    public ObisHandler(TelegramClient telegramClient) {
        super(telegramClient);
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            update.getMessage().getText().equals("🔐 OBIS");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerTextMessage(update, "Меню OBIS", MARKUP);
    }
}
