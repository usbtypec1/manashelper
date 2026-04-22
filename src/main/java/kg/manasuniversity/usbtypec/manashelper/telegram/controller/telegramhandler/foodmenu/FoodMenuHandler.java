package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.foodmenu;

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
public class FoodMenuHandler implements TelegramUpdateHandler {
    private static final String TEXT = """
        <b>🤤 Просмотр меню в йемекхане:</b>
        
        🍏 На сегодня:
        <code>/yemek today</code>
        
        🍏 На завтра:
        <code>/yemek tomorrow</code>
        
        🧐 Так же можно просматривать на N дней вперёд:
        <code>/yemek {N}</code>
        
        Например👇
        🍎 На послезавтра - <code>/yemek 2</code>
        🍎 10 дней вперёд - <code>/yemek 10</code>
        """;
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("🕧 Сегодня")
                    .callbackData("food_menu:today")
                    .build(),
                InlineKeyboardButton.builder()
                    .text("🕒 Завтра")
                    .callbackData("food_menu:tomorrow")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("🕜 Послезавтра")
                    .callbackData("food_menu:after_tomorrow")
                    .build()
            )
        )
        .build();

    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isMessageTextEquals(update, "🍉 Йемек") || isMessageTextEquals(update, "/yemek");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerUtils.answerTextMessage(update, TEXT, MARKUP);
    }
}
