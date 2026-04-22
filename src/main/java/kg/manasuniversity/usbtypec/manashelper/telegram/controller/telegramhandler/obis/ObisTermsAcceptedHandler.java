package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.KeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.KeyboardRow;
import org.telegram.telegrambots.meta.api.objects.webapp.WebAppInfo;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isCallbackDataEquals;

@Component
@RequiredArgsConstructor
public class ObisTermsAcceptedHandler implements TelegramUpdateHandler {
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isCallbackDataEquals(update, "obis:accept_terms");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        ReplyKeyboardMarkup markup = ReplyKeyboardMarkup.builder()
            .keyboardRow(
                new KeyboardRow(
                    KeyboardButton.builder()
                        .text("Ввести данные")
                        .webApp(new WebAppInfo("https://manashelper-obis-credentials-form.vercel.app"))
                        .build()
                )
            )
            .build();
        answerUtils.answerTextMessage(update, "Введите данные", markup);
    }
}
