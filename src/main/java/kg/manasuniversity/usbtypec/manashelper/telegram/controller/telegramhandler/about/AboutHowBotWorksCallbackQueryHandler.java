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
public class AboutHowBotWorksCallbackQueryHandler extends TelegramUpdateHandler {
    private static final String TEXT = """
        Как работает бот (технически)
        
        Реализован на Java с использованием Spring Boot.
        
        📂 Открытый исходный код: GitHub (https://github.com/usbtypec1/manashelper)
        
        Любой желающий может изучить код и убедиться, как именно работает бот.
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

    public AboutHowBotWorksCallbackQueryHandler(TelegramClient telegramClient) {
        super(telegramClient);
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals("about:how_bot_works");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        editTextMessage(update, TEXT, MARKUP);
    }
}
