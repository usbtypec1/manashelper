package kg.manasuniversity.usbtypec.manashelper.controller;

import kg.usbtypec.telegramfsm.core.engine.FlowManager;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

/**
 * Entry point of the {@code obisCredentialsFlow} (see {@link ObisCredentialsFlowConfiguration}): shows the
 * terms and, once shown, starts the flow so the next "accept terms" button press is routed to
 * {@link ObisAcceptTermsStepHandler} instead of being handled ad hoc.
 */
@Component
public class ObisCredentialsHandler extends TelegramUpdateHandler {
    private static final String TEXT = "Пожалуйста, примите условия использования бота, чтобы продолжить.";
    private static final InlineKeyboardMarkup MARKUP = InlineKeyboardMarkup.builder()
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("📃 Условия использования")
                    .url("https://telegra.ph/Polzovatelskoe-soglashenie-manas-helper-bot-01-13")
                    .build()
            )
        )
        .keyboardRow(
            new InlineKeyboardRow(
                InlineKeyboardButton.builder()
                    .text("✅ Принять условия")
                    .callbackData("obis:accept_terms")
                    .build()
            )
        )
        .build();

    private final FlowManager flowManager;

    public ObisCredentialsHandler(TelegramClient telegramClient, FlowManager flowManager) {
        super(telegramClient);
        this.flowManager = flowManager;
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals("obis:credentials");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        answerTextMessage(update, TEXT, MARKUP);
        flowManager.start("obisCredentialsFlow", getChatId(update));
    }
}
