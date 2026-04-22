package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.foodmenu;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.service.DailyMenuService;
import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.FoodMenuFormatter;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.FoodMenuRatingCallbackDataFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenuInfo;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMediaGroup;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.media.InputMediaPhoto;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;
import java.util.regex.Pattern;
import java.util.stream.IntStream;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateUtils.getUserId;

@Component
@RequiredArgsConstructor
public class FoodMenuCommandHandler implements TelegramUpdateHandler {
    private static final Pattern PATTERN = Pattern.compile("/yemek (today|tomorrow|\\d+)");

    private final DailyMenuService dailyMenuService;
    private final AnswerUtils answerUtils;
    private final TelegramClient telegramClient;

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            PATTERN.matcher(update.getMessage().getText()).matches();
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        String text = update.getMessage().getText();
        String[] parts = text.split(" ");
        int skipDays = switch (parts[1]) {
            case "today" -> 0;
            case "tomorrow" -> 1;
            default -> Integer.parseInt(parts[1]);
        };

        Long userId = getUserId(update);

        DailyMenuInfo dailyMenu;
        try {
            dailyMenu = dailyMenuService.getDailyMenuBySkippingDays(skipDays, userId);
        } catch (DailyMenuNotFoundException e) {
            answerUtils.answerTextMessage(update, FoodMenuFormatter.formatNotFound(skipDays));
            return;
        }
        String answerText = FoodMenuFormatter.format(dailyMenu);

        List<InputMediaPhoto> photos = FoodMenuFormatter.buildPhotos(answerText, dailyMenu);

        SendMediaGroup sendMediaGroup = SendMediaGroup.builder()
            .medias(photos)
            .chatId(update.getMessage().getChatId())
            .build();
        telegramClient.execute(sendMediaGroup);

        List<InlineKeyboardRow> rows = List.of(
            new InlineKeyboardRow(
                IntStream.rangeClosed(1, 5)
                    .mapToObj(i -> InlineKeyboardButton.builder()
                        .text(String.valueOf(i))
                        .callbackData(FoodMenuRatingCallbackDataFilter.pack(dailyMenu.id(), i))
                        .build()
                    )
                    .toArray(InlineKeyboardButton[]::new)
            )
        );
        InlineKeyboardMarkup markup = InlineKeyboardMarkup.builder().keyboard(rows).build();
        answerUtils.answerTextMessage(update, "Поставьте вашу оценку", markup);
    }
}
