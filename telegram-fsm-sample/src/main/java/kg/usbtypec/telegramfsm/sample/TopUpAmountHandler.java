package kg.usbtypec.telegramfsm.sample;

import kg.usbtypec.telegramfsm.core.FlowContext;
import kg.usbtypec.telegramfsm.core.MessageHandler;
import kg.usbtypec.telegramfsm.core.RetryStepException;
import kg.usbtypec.telegramfsm.core.callback.CallbackData;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.math.BigDecimal;

@Component
public class TopUpAmountHandler implements MessageHandler {

    private final TelegramClient telegramClient;

    public TopUpAmountHandler(TelegramClient telegramClient) {
        this.telegramClient = telegramClient;
    }

    @Override
    public void handle(Message message, FlowContext context) throws TelegramApiException {
        BigDecimal amount;
        try {
            amount = new BigDecimal(message.getText().trim());
        } catch (NumberFormatException e) {
            telegramClient.execute(SendMessage.builder()
                    .chatId(message.getChatId())
                    .text("That doesn't look like a number, please try again, e.g. 100.50")
                    .build());
            throw new RetryStepException("invalid amount");
        }
        context.put("amount", amount);

        InlineKeyboardButton confirmButton = InlineKeyboardButton.builder()
                .text("Confirm")
                .callbackData(CallbackData.join("confirm", amount))
                .build();
        InlineKeyboardButton cancelButton = InlineKeyboardButton.builder()
                .text("Cancel")
                .callbackData(CallbackData.join("cancel"))
                .build();
        InlineKeyboardMarkup keyboard = InlineKeyboardMarkup.builder()
                .keyboardRow(new InlineKeyboardRow(confirmButton, cancelButton))
                .build();

        telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("Top up %s? Press a button below.".formatted(amount))
                .replyMarkup(keyboard)
                .build());
    }
}
