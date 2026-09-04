package kg.manasuniversity.usbtypec.manashelper.controller;

import kg.usbtypec.telegramfsm.core.CallbackQueryHandler;
import kg.usbtypec.telegramfsm.core.FlowContext;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.ReplyKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.KeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.KeyboardRow;
import org.telegram.telegrambots.meta.api.objects.webapp.WebAppInfo;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

/**
 * First step of the {@code obisCredentialsFlow} (see {@link ObisCredentialsFlowConfiguration}): reacts to the
 * "accept terms" button pressed after {@link ObisCredentialsHandler} started the flow, and hands the user a
 * reply keyboard opening the OBIS credentials web app.
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
        ReplyKeyboardMarkup markup = ReplyKeyboardMarkup.builder()
            .keyboardRow(
                new KeyboardRow(
                    KeyboardButton.builder()
                        .text("Ввести данные")
                        .webApp(new WebAppInfo("https://manashelper-obis-credentials-form.vercel.app"))
                        .build()
                )
            )
            .build();
        telegramClient.execute(SendMessage.builder()
            .chatId(callbackQuery.getMessage().getChatId())
            .text("Введите данные")
            .replyMarkup(markup)
            .build());
    }
}
