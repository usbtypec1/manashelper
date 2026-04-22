package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.foodmenu;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.service.DailyMenuService;
import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.FoodMenuFormatter;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.FoodMenuRatingCallbackDataFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenuInfo;
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
import java.util.stream.IntStream;

@Component
public class FoodMenuCallbackQueryHandler extends TelegramUpdateHandler {
    private final DailyMenuService dailyMenuService;

    public FoodMenuCallbackQueryHandler(TelegramClient telegramClient, DailyMenuService dailyMenuService) {
        super(telegramClient);
        this.dailyMenuService = dailyMenuService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        if (!update.hasCallbackQuery()) {
            return false;
        }
        String callbackData = update.getCallbackQuery().getData();
        return callbackData.equals("food_menu:today") ||
            callbackData.equals("food_menu:tomorrow") ||
            callbackData.equals("food_menu:after_tomorrow");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = getUserId(update);
        String callbackData = update.getCallbackQuery().getData();
        int skipDays = switch (callbackData) {
            case "food_menu:today" -> 0;
            case "food_menu:tomorrow" -> 1;
            case "food_menu:after_tomorrow" -> 2;
            default -> throw new IllegalStateException("Unexpected value: " + callbackData);
        };
        DailyMenuInfo dailyMenu;
        try {
            dailyMenu = dailyMenuService.getDailyMenuBySkippingDays(skipDays, userId);
        } catch (DailyMenuNotFoundException e) {
            answerTextMessage(update, FoodMenuFormatter.formatNotFound(skipDays));
            return;
        }
        String answerText = FoodMenuFormatter.format(dailyMenu);

        List<InputMediaPhoto> photos = FoodMenuFormatter.buildPhotos(answerText, dailyMenu);

        SendMediaGroup sendMediaGroup = SendMediaGroup.builder()
            .medias(photos)
            .chatId(update.getCallbackQuery().getMessage().getChatId())
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
        answerTextMessage(update, "Поставьте вашу оценку", markup);
    }
}
