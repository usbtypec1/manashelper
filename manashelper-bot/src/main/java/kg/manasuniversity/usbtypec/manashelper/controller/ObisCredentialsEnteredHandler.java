package kg.manasuniversity.usbtypec.manashelper.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import kg.manasuniversity.usbtypec.manashelper.exception.ObisLoginException;
import kg.manasuniversity.usbtypec.manashelper.service.UserService;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class ObisCredentialsEnteredHandler extends TelegramUpdateHandler {
    private final ObjectMapper objectMapper;
    private final UserService userService;

    public ObisCredentialsEnteredHandler(TelegramClient telegramClient, UserService userService) {
        super(telegramClient);
        objectMapper = new ObjectMapper();
        this.userService = userService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        if (!update.hasMessage()) {
            return false;
        }
        return update.getMessage().hasWebAppData()
            && update.getMessage().getWebAppData().getButtonText().equals("Ввести данные");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = update.getMessage().getFrom().getId();
        String webAppData = update.getMessage().getWebAppData().getData();
        try {
            ObisCredentials obisCredentials = objectMapper.readValue(webAppData, ObisCredentials.class);
            userService.updateUserCredentials(userId, obisCredentials.studentNumber(), obisCredentials.password());
            answerTextMessage(update, "Данные успешно сохранены");
        } catch (JsonProcessingException e) {
            throw new RuntimeException(e);
        } catch (ObisLoginException _) {
            answerTextMessage(update, "Неверные данные от OBIS");
        }
    }

    record ObisCredentials(String studentNumber, String password) {
    }
}
