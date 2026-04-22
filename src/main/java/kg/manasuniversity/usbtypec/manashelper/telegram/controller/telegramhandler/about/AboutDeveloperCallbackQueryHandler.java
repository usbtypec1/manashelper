package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.about;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isCallbackDataEquals;

@Component
@RequiredArgsConstructor
public class AboutDeveloperCallbackQueryHandler implements TelegramUpdateHandler {
    private static final String TEXT = """
        Кто сделал этого бота?
        
        Меня зовут Элдос Бактыбек уулу, я студент 3 курса Кыргызско-Турецкого Университета Манас, Java разработчик.
        
        Я создал этого бота, чтобы помочь студентам легче справляться с учебными задачами и быть в курсе всех изменений.
        
        Если у тебя есть вопросы или предложения, или вы нашли ошибку в работе бота, можете связаться со мной:
        • 📨 Telegram: @usbtypec
        • 📧 Email: eldos.baktybekov@gmail.com
        """;

    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isCallbackDataEquals(update, "about:developer");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerUtils.answerTextMessage(update, TEXT);
        answerUtils.answerEmptyCallbackQuery(update);
    }
}
