package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.about;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class AboutHandler extends TelegramUpdateHandler {
    private static final String TEXT = """
        Привет друг 👋
        
        Этот бот создан специально для студентов <b>Кыргызско-Турецкого Университета Манас.</b>
        
        <b>Что умеет бот:</b>
        • 📊 <b>Йоклама и экзамены</b> - просмотр оценок и йокламы
        • 🔔 <b>Уведомления</b> об изменениях йокламы
        • 📝 <b>Оценки экзаменов</b> - узнавай сразу после выставления
        • 🍽 <b>Меню йемекхане</b> - актуальное меню на день
        • ⭐️ <b>Оценка еды</b> - ставь и смотри рейтинги блюд
        • 📅 <b>Расписание занятий</b> и уведомления об изменениях
        """;
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("Зачем боту пароль от OBIS?")
                    .callbackData("about:obis")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("Как работает бот? (Для задротов)")
                    .callbackData("about:how_bot_works")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("Кто сделал этого бота?")
                    .callbackData("about:developer")
                    .build()
            )
        )
        .build();

    public AboutHandler(TelegramClient telegramClient) {
        super(telegramClient);
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerTextMessage(update, TEXT, MARKUP);
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            update.getMessage().getText().equals("ℹ️ О боте");
    }
}
