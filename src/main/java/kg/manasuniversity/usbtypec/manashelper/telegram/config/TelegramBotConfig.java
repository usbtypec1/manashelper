package kg.manasuniversity.usbtypec.manashelper.telegram.config;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramConsumer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.telegram.telegrambots.client.okhttp.OkHttpTelegramClient;
import org.telegram.telegrambots.longpolling.TelegramBotsLongPollingApplication;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

@Configuration
public class TelegramBotConfig {
    @Value("${telegram.bot.token}")
    private String telegramBotToken;

    private final TelegramConsumer telegramConsumer;

    public TelegramBotConfig(@Lazy TelegramConsumer telegramConsumer) {
        this.telegramConsumer = telegramConsumer;
    }

    @Bean
    public TelegramBotsLongPollingApplication telegramBotsLongPollingApplication() throws TelegramApiException {
        TelegramBotsLongPollingApplication application = new TelegramBotsLongPollingApplication();
        application.registerBot(telegramBotToken, telegramConsumer);
        return application;
    }

    @Bean("telegramApiClient")
    public TelegramClient telegramClient() {
        return new OkHttpTelegramClient(telegramBotToken);
    }
}
