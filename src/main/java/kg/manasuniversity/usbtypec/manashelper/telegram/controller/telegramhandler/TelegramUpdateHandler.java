package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler;

import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

public interface TelegramUpdateHandler {

    boolean shouldHandle(Update update);

    void handle(Update update) throws TelegramApiException;
}
