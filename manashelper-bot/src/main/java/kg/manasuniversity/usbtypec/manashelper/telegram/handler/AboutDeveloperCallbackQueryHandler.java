package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class AboutDeveloperCallbackQueryHandler extends TelegramUpdateHandler {
    private static final String TEXT = """
        Кто сделал этого бота?
        
        Меня зовут Элдос Бактыбек уулу, я студент 3 курса Кыргызско-Турецкого Университета Манас, веб-разработчик.
        
        Я создал этого бота, чтобы помочь студентам легче справляться с учебными задачами и быть в курсе всех изменений.
        
        Если у тебя есть вопросы или предложения, или вы нашли ошибку в работе бота, можете связаться со мной:
        • 📨 Telegram: @usbtypec
        • 📧 Email: eldos.baktybekov@gmail.com
        """;

    public AboutDeveloperCallbackQueryHandler(TelegramClient telegramClient) {
        super(telegramClient);
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals("about:developer");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerTextMessage(update, TEXT);
    }
}
