package kg.manasuniversity.usbtypec.manashelper.controller;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import kg.manasuniversity.usbtypec.manashelper.exception.ObisLoginException;
import kg.manasuniversity.usbtypec.manashelper.service.UserService;
import kg.usbtypec.telegramfsm.core.FlowContext;
import kg.usbtypec.telegramfsm.core.MessageHandler;
import kg.usbtypec.telegramfsm.core.RetryStepException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

/**
 * Final step of the {@code obisCredentialsFlow} (see {@link ObisCredentialsFlowConfiguration}): reads the
 * credentials submitted through the web app opened by {@link ObisAcceptTermsStepHandler} and saves them.
 * Invalid JSON or a failed OBIS login re-prompts on the same step instead of ending the flow.
 */
@Component
public class ObisCredentialsSubmittedStepHandler implements MessageHandler {

    private final TelegramClient telegramClient;
    private final UserService userService;
    private final ObjectMapper objectMapper;

    public ObisCredentialsSubmittedStepHandler(
        @Qualifier("telegramApiClient") TelegramClient telegramClient,
        UserService userService
    ) {
        this.telegramClient = telegramClient;
        this.userService = userService;
        this.objectMapper = new ObjectMapper();
    }

    @Override
    public boolean matches(Message message, FlowContext context) {
        return message.hasWebAppData() && "Ввести данные".equals(message.getWebAppData().getButtonText());
    }

    @Override
    public void handle(Message message, FlowContext context) throws TelegramApiException {
        Long userId = message.getFrom().getId();
        String webAppData = message.getWebAppData().getData();
        try {
            ObisCredentials credentials = objectMapper.readValue(webAppData, ObisCredentials.class);
            userService.updateUserCredentials(userId, credentials.studentNumber(), credentials.password());
            telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("Данные успешно сохранены")
                .build());
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Malformed OBIS credentials web app payload", e);
        } catch (ObisLoginException e) {
            telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("Неверные данные от OBIS")
                .build());
            throw new RetryStepException("invalid OBIS credentials");
        }
    }

    private record ObisCredentials(String studentNumber, String password) {
    }
}
