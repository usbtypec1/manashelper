package kg.usbtypec.telegramfsm.sample;

import kg.usbtypec.telegramfsm.core.FlowContext;
import kg.usbtypec.telegramfsm.core.MessageHandler;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Component
public class TopUpStartHandler implements MessageHandler {

    private final TelegramClient telegramClient;

    public TopUpStartHandler(TelegramClient telegramClient) {
        this.telegramClient = telegramClient;
    }

    @Override
    public void handle(Message message, FlowContext context) throws TelegramApiException {
        telegramClient.execute(SendMessage.builder()
                .chatId(message.getChatId())
                .text("How much would you like to top up?")
                .build());
    }
}
