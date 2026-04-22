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
public class AboutHowBotWorksCallbackQueryHandler implements TelegramUpdateHandler {
    private static final String TEXT = """
        Как работает бот (технически)
        
        Реализован на Java с использованием Spring Boot.
        
        📂 Открытый исходный код: GitHub (https://github.com/usbtypec1/manashelper)
        
        Любой желающий может изучить код и убедиться, как именно работает бот.
        """;

    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isCallbackDataEquals(update, "about:how_bot_works");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerUtils.answerTextMessage(update, TEXT);
        answerUtils.answerEmptyCallbackQuery(update);
    }
}
