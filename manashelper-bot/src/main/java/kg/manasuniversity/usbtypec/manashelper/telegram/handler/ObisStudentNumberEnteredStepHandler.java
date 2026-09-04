package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

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

/**
 * Second step of the {@code obisCredentialsFlow} (see {@link ObisCredentialsFlowConfiguration}): reads the
 * student number typed after {@link ObisAcceptTermsStepHandler} asked for it, stashes it in the flow context for
 * {@link ObisPasswordEnteredStepHandler}, and asks for the password next.
 */
@Component
public class ObisStudentNumberEnteredStepHandler implements MessageHandler {

    static final String STUDENT_NUMBER_CONTEXT_KEY = "studentNumber";

    private final TelegramClient telegramClient;

    public ObisStudentNumberEnteredStepHandler(@Qualifier("telegramApiClient") TelegramClient telegramClient) {
        this.telegramClient = telegramClient;
    }

    @Override
    public boolean matches(Message message, FlowContext context) {
        return message.hasText();
    }

    @Override
    public void handle(Message message, FlowContext context) throws TelegramApiException {
        String studentNumber = message.getText().trim();
        if (studentNumber.isEmpty()) {
            telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("Студенческий номер не может быть пустым. Введите ваш студенческий номер:")
                .build());
            throw new RetryStepException("blank student number");
        }
        context.put(STUDENT_NUMBER_CONTEXT_KEY, studentNumber);
        telegramClient.execute(SendMessage.builder()
            .chatId(message.getChatId())
            .text("Введите ваш пароль:")
            .build());
    }
}
