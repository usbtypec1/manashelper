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

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isCallbackDataEquals;

@Component
@RequiredArgsConstructor
public class ObisCredentialsHandler implements TelegramUpdateHandler {
    private static final String TEXT = "Пожалуйста, примите условия использования бота, чтобы продолжить.";
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("📃 Условия использования")
                    .url("https://telegra.ph/Polzovatelskoe-soglashenie-manas-helper-bot-01-13")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("✅ Принять условия")
                    .callbackData("obis:accept_terms")
                    .build()
            )
        )
        .build();

    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isCallbackDataEquals(update, "obis:credentials");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerUtils.answerTextMessage(update, TEXT, MARKUP);
    }
}
