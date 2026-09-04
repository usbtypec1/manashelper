package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import kg.manasuniversity.usbtypec.manashelper.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.service.DailyMenuService;
import kg.manasuniversity.usbtypec.manashelper.service.FoodMenuFormatter;
import kg.manasuniversity.usbtypec.manashelper.service.FoodMenuRatingCallbackDataFilter;
import kg.manasuniversity.usbtypec.manashelper.model.DailyMenuModel;
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

@Component
public class FoodMenuCommandHandler extends TelegramUpdateHandler {
    private static final Pattern PATTERN = Pattern.compile("/yemek (today|tomorrow|\\d+)");
    private final DailyMenuService dailyMenuService;

    public FoodMenuCommandHandler(TelegramClient telegramClient, DailyMenuService dailyMenuService) {
        super(telegramClient);
        this.dailyMenuService = dailyMenuService;
    }

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

        DailyMenuModel dailyMenuModel;
        try {
            dailyMenuModel = dailyMenuService.getDailyMenuBySkippingDays(skipDays);
        } catch (DailyMenuNotFoundException _) {
            answerTextMessage(update, FoodMenuFormatter.formatNotFound(skipDays));
            return;
        }
        String answerText = FoodMenuFormatter.format(dailyMenuModel);

        List<InputMediaPhoto> photos = FoodMenuFormatter.buildPhotos(answerText, dailyMenuModel);

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
                        .callbackData(FoodMenuRatingCallbackDataFilter.pack(dailyMenuModel.id(), i))
                        .build()
                    )
                    .toArray(InlineKeyboardButton[]::new)
            )
        );
        InlineKeyboardMarkup markup = InlineKeyboardMarkup.builder().keyboard(rows).build();
        answerTextMessage(update, "Поставьте вашу оценку", markup);
    }
}
