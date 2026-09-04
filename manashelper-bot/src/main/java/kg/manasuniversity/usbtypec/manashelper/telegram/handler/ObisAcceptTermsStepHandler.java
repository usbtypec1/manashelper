package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import kg.manasuniversity.usbtypec.manashelper.telegram.flow.ObisCredentialsFlowConfiguration;
import kg.usbtypec.telegramfsm.core.CallbackQueryHandler;
import kg.usbtypec.telegramfsm.core.FlowContext;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

/**
 * First step of the {@code obisCredentialsFlow} (see {@link ObisCredentialsFlowConfiguration}): reacts to the
 * "accept terms" button pressed after {@link ObisCredentialsHandler} started the flow, and asks the user to
 * type their OBIS student number next.
 */
@Component
public class ObisAcceptTermsStepHandler implements CallbackQueryHandler {

    private final TelegramClient telegramClient;

    public ObisAcceptTermsStepHandler(@Qualifier("telegramApiClient") TelegramClient telegramClient) {
        this.telegramClient = telegramClient;
    }

    @Override
    public boolean matches(CallbackQuery callbackQuery, FlowContext context) {
        return "obis:accept_terms".equals(callbackQuery.getData());
    }

    @Override
    public void handle(CallbackQuery callbackQuery, FlowContext context) throws TelegramApiException {
        telegramClient.execute(SendMessage.builder()
            .chatId(callbackQuery.getMessage().getChatId())
            .text("Введите ваш студенческий номер:")
            .build());
    }
}
