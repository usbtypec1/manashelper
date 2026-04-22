package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isMessageTextEquals;

@Component
@RequiredArgsConstructor
public class ObisHandler implements TelegramUpdateHandler {
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

    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isMessageTextEquals(update, "🔐 OBIS");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerUtils.answerTextMessage(update, "Меню OBIS", MARKUP);
    }
}
