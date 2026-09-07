package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.util.UpdateType;

public final class UpdateUtils {

    private UpdateUtils() {
    }

    public static Long getChatId(Update update) {
        return switch (UpdateType.from(update)) {
            case MESSAGE -> update.getMessage().getChatId();
            case CALLBACK_QUERY -> update.getCallbackQuery().getMessage().getChatId();
            default -> throw new IllegalArgumentException("Unknown update type");
        };
    }
}
