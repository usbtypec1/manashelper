package kg.usbtypec.telegramfsm.sample;

import kg.usbtypec.telegramfsm.core.engine.FlowEngine;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.longpolling.interfaces.LongPollingUpdateConsumer;
import org.telegram.telegrambots.longpolling.starter.SpringLongPollingBot;
import org.telegram.telegrambots.meta.api.objects.Update;

import java.util.List;

/**
 * All this bot does is hand every update to the {@link FlowEngine}; the actual conversation (asking for an
 * amount, confirming with a button) lives entirely in {@link TopUpFlowConfiguration} and its handlers.
 * Being a {@link SpringLongPollingBot} bean is enough for {@code telegrambots-springboot-longpolling-starter}
 * to register and start it automatically.
 */
@Component
public class TopUpBot implements SpringLongPollingBot, LongPollingUpdateConsumer {

    private final FlowEngine flowEngine;
    private final String botToken;

    public TopUpBot(FlowEngine flowEngine, @Value("${telegram.bot.token}") String botToken) {
        this.flowEngine = flowEngine;
        this.botToken = botToken;
    }

    @Override
    public String getBotToken() {
        return botToken;
    }

    @Override
    public LongPollingUpdateConsumer getUpdatesConsumer() {
        return this;
    }

    @Override
    public void consume(List<Update> updates) {
        updates.forEach(flowEngine::dispatch);
    }
}
