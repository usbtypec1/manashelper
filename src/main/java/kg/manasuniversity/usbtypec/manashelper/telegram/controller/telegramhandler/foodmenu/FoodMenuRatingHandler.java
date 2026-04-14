package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.foodmenu;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.model.FoodMenuRating;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.service.DailyMenuService;
import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.FoodMenuRatingCallbackDataFilter;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.AnswerCallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class FoodMenuRatingHandler extends TelegramUpdateHandler {
    private final DailyMenuService dailyMenuService;

    public FoodMenuRatingHandler(TelegramClient telegramClient, DailyMenuService dailyMenuService) {
        super(telegramClient);
        this.dailyMenuService = dailyMenuService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasCallbackQuery()
            && FoodMenuRatingCallbackDataFilter.parse(update.getCallbackQuery().getData()).isPresent();
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        String callbackData = update.getCallbackQuery().getData();
        FoodMenuRating foodMenuRating = FoodMenuRatingCallbackDataFilter.parse(callbackData).get();
        Long userId = update.getCallbackQuery().getFrom().getId();
        dailyMenuService.setRating(userId, foodMenuRating);
        AnswerCallbackQuery answerCallbackQuery = AnswerCallbackQuery.builder()
            .text("❤️ Спасибо за вашу оценку")
            .showAlert(true)
            .callbackQueryId(update.getCallbackQuery().getId())
            .build();
        telegramClient.execute(answerCallbackQuery);
    }
}
