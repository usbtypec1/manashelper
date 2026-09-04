package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import kg.manasuniversity.usbtypec.manashelper.exception.ObisLoginException;
import kg.manasuniversity.usbtypec.manashelper.service.UserService;
import kg.manasuniversity.usbtypec.manashelper.telegram.flow.ObisCredentialsFlowConfiguration;
import kg.usbtypec.telegramfsm.core.FlowContext;
import kg.usbtypec.telegramfsm.core.MessageHandler;
import kg.usbtypec.telegramfsm.core.RetryStepException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import static kg.manasuniversity.usbtypec.manashelper.telegram.handler.ObisStudentNumberEnteredStepHandler.STUDENT_NUMBER_CONTEXT_KEY;

/**
 * Final step of the {@code obisCredentialsFlow} (see {@link ObisCredentialsFlowConfiguration}): reads the
 * password typed after {@link ObisStudentNumberEnteredStepHandler} asked for it, pairs it with the student
 * number stashed in the flow context, and saves the credentials. A failed OBIS login re-prompts for the
 * password on the same step instead of ending the flow.
 */
@Component
public class ObisPasswordEnteredStepHandler implements MessageHandler {

    private final TelegramClient telegramClient;
    private final UserService userService;

    public ObisPasswordEnteredStepHandler(
        @Qualifier("telegramApiClient") TelegramClient telegramClient,
        UserService userService
    ) {
        this.telegramClient = telegramClient;
        this.userService = userService;
    }

    @Override
    public boolean matches(Message message, FlowContext context) {
        return message.hasText();
    }

    @Override
    public void handle(Message message, FlowContext context) throws TelegramApiException {
        String studentNumber = context.get(STUDENT_NUMBER_CONTEXT_KEY);
        String password = message.getText();
        try {
            userService.updateUserCredentials(message.getFrom().getId(), studentNumber, password);
            telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("Данные успешно сохранены")
                .build());
        } catch (ObisLoginException e) {
            telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("Неверные данные от OBIS. Введите пароль ещё раз:")
                .build());
            throw new RetryStepException("invalid OBIS credentials");
        }
    }
}
