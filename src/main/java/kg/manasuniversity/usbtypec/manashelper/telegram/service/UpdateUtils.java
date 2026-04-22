package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import org.telegram.telegrambots.meta.api.objects.Update;

public class UpdateUtils {
    public static Long getChatId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getChatId();
        } else if (update.hasCallbackQuery()) {
            return update.getCallbackQuery().getMessage().getChatId();
        }
        throw new IllegalArgumentException("Unknown update type");
    }

    public static Long getUserId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getFrom().getId();
        } else if (update.hasCallbackQuery()) {
            return update.getCallbackQuery().getFrom().getId();
        }
        throw new IllegalArgumentException("Unknown update type");
    }

    public static Integer getMessageId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getMessageId();
        } else if (update.hasCallbackQuery()) {
            return update.getCallbackQuery().getMessage().getMessageId();
        }
        throw new IllegalArgumentException("Unknown update type");
    }
}
