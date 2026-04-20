package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler;

import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.user.service.UserService;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.User;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class StartCommandHandler extends TelegramUpdateHandler {
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("🍉 Йемек")
                    .callbackData("food_menu")
                    .build(),
                InlineKeyboardButton.builder()
                    .text("🔐 OBIS")
                    .callbackData("obis")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("📅 Расписание")
                    .callbackData(CallbackData.FACULTY_LIST.name())
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("ℹ️ О боте")
                    .callbackData("about")
                    .build()
            )
        )
        .build();
    private final UserService userService;

    public StartCommandHandler(TelegramClient telegramClient, UserService userService) {
        super(telegramClient);
        this.userService = userService;
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        User user = update.getMessage().getFrom();
        String fullName = user.getFirstName();
        if (user.getLastName() != null) {
            fullName = user.getFirstName() + " " + user.getLastName();
        }
        userService.upsertUser(user.getId(), fullName, user.getUserName());
        answerTextMessage(update, "Главное меню", MARKUP);
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            update.getMessage().getText().equals("/start");
    }
}
