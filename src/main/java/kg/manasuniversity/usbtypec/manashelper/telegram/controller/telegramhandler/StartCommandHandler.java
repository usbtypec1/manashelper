package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler;

import kg.manasuniversity.usbtypec.manashelper.user.service.UserService;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.User;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.KeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.KeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class StartCommandHandler extends TelegramUpdateHandler {
    private static final ReplyKeyboardMarkup MARKUP = ReplyKeyboardMarkup.builder()
        .resizeKeyboard(true)
        .isPersistent(true)
        .keyboardRow(
            new KeyboardRow(
                new KeyboardButton("🍉 Йемек"),
                new KeyboardButton("🔐 OBIS")
            )
        )
        .keyboardRow(
            new KeyboardRow(
                new KeyboardButton("📅 Расписание")
            )
        )
        .keyboardRow(
            new KeyboardRow(
                new KeyboardButton("ℹ️ О боте")
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
