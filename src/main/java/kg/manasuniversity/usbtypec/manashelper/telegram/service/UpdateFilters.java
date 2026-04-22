package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import org.telegram.telegrambots.meta.api.objects.Update;

public class UpdateFilters {
    public static boolean isMessageTextEquals(Update update, String text) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            update.getMessage().getText().equals(text);
    }

    public static boolean isCallbackDataEquals(Update update, String callbackData) {
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals(callbackData);
    }

    public static boolean isMessageWebAppButtonTextEquals(Update update, String buttonText) {
        return update.hasMessage() &&
            update.getMessage().hasWebAppData() &&
            update.getMessage().getWebAppData().getButtonText().equals(buttonText);
    }
}
