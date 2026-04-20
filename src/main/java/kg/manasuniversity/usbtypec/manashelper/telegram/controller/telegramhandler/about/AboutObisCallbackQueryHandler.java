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
public class AboutObisCallbackQueryHandler extends TelegramUpdateHandler {
    private static final String TEXT_TEMPLATE = """
        <b>Зачем боту нужен пароль от OBIS?</b>
        
        Чтобы бот мог:
        • 📊 получать ваши оценки
        • 🔔 уведомлять об их изменениях
        
        ему необходим доступ к вашей учетной записи в OBIS.
        
        <b>Безопасность данных</b>
        Ваши логин и пароль:
        • 🔐 хранятся <u>в зашифрованном виде</u>
        • ❌ не передаются третьим лицам
        • ✅ используются <u>только</u> для работы с OBIS от вашего имени
        
        <b>Немного статистики</b>
        • 👥 {credentialsCount} из {totalUsersCount} пользователей ({percentage}%) уже доверили боту свои данные.
        """;
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("🔙 Назад")
                    .callbackData("about")
                    .build()
            )
        )
        .build();

    public AboutObisCallbackQueryHandler(TelegramClient telegramClient) {
        super(telegramClient);
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals("about:obis");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        String text = TEXT_TEMPLATE
            .replace("{credentialsCount}", "0")
            .replace("{totalUsersCount}", "0")
            .replace("{percentage}", "0");
        editTextMessage(update, text, MARKUP);
    }
}
