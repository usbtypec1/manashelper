package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.user.exception.ObisLoginException;
import kg.manasuniversity.usbtypec.manashelper.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isMessageWebAppButtonTextEquals;

@Component
@RequiredArgsConstructor
public class ObisCredentialsEnteredHandler implements TelegramUpdateHandler {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final UserService userService;
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isMessageWebAppButtonTextEquals(update, "Ввести данные");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = update.getMessage().getFrom().getId();
        String webAppData = update.getMessage().getWebAppData().getData();
        try {
            ObisCredentials obisCredentials = objectMapper.readValue(webAppData, ObisCredentials.class);
            userService.updateUserCredentials(userId, obisCredentials.studentNumber(), obisCredentials.password());
            answerUtils.answerTextMessage(update, "Данные успешно сохранены");
        } catch (JsonProcessingException e) {
            throw new RuntimeException(e);
        } catch (ObisLoginException e) {
            answerUtils.answerTextMessage(update, "Неверные данные от OBIS");
        }
    }

    record ObisCredentials(String studentNumber, String password) {
    }
}
