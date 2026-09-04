package kg.usbtypec.telegramfsm.sample;

import kg.usbtypec.telegramfsm.core.engine.FlowEngine;
import kg.usbtypec.telegramfsm.spring.autoconfigure.InMemoryStateStoreAutoConfiguration;
import kg.usbtypec.telegramfsm.spring.autoconfigure.TelegramFsmAutoConfiguration;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.telegram.telegrambots.meta.api.methods.AnswerCallbackQuery;
import org.telegram.telegrambots.meta.api.methods.botapimethods.BotApiMethod;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.chat.Chat;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

/**
 * Drives the sample top-up flow end to end (command -> amount -> button press) through the real
 * {@link TopUpFlowConfiguration} and handler beans, with a mocked {@link TelegramClient} so no network calls
 * are made.
 */
class TopUpFlowIntegrationTest {

    private static final long CHAT_ID = 777L;

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(
                    TelegramFsmAutoConfiguration.class,
                    InMemoryStateStoreAutoConfiguration.class))
            .withUserConfiguration(
                    TopUpFlowConfiguration.class,
                    TopUpStartHandler.class,
                    TopUpAmountHandler.class,
                    TopUpConfirmHandler.class,
                    TopUpCancelHandler.class,
                    MockTelegramClientConfig.class);

    @Test
    void wholeConversationCompletesAndSendsExpectedMessages() {
        contextRunner.run(context -> {
            FlowEngine engine = context.getBean(FlowEngine.class);
            TelegramClient telegramClient = context.getBean(TelegramClient.class);

            assertThat(engine.dispatch(messageUpdate("/topup"))).isTrue();
            assertThat(engine.dispatch(messageUpdate("not-a-number"))).isTrue();
            assertThat(engine.dispatch(messageUpdate("150.00"))).isTrue();
            assertThat(engine.dispatch(callbackQueryUpdate("confirm:150.00"))).isTrue();

            @SuppressWarnings({"unchecked", "rawtypes"})
            ArgumentCaptor<BotApiMethod> captor = ArgumentCaptor.forClass(BotApiMethod.class);
            verify(telegramClient, times(5)).execute(captor.capture());
            List<?> calls = captor.getAllValues();

            assertThat(calls).hasSize(5);
            assertThat(text(calls.get(0))).isEqualTo("How much would you like to top up?");
            assertThat(text(calls.get(1))).isEqualTo("That doesn't look like a number, please try again, e.g. 100.50");
            assertThat(text(calls.get(2))).isEqualTo("Top up 150.00? Press a button below.");
            assertThat(calls.get(3)).isInstanceOf(AnswerCallbackQuery.class);
            assertThat(text(calls.get(4))).isEqualTo("Top up of 150.00 confirmed!");
        });
    }

    /**
     * The confirm and cancel handlers sit on the same step; each has its own filter on the callback data, so
     * pressing "Cancel" must route to {@link TopUpCancelHandler} instead of {@link TopUpConfirmHandler}.
     */
    @Test
    void cancelButtonIsRoutedToCancelHandlerNotConfirmHandler() {
        contextRunner.run(context -> {
            FlowEngine engine = context.getBean(FlowEngine.class);
            TelegramClient telegramClient = context.getBean(TelegramClient.class);

            assertThat(engine.dispatch(messageUpdate("/topup"))).isTrue();
            assertThat(engine.dispatch(messageUpdate("150.00"))).isTrue();
            assertThat(engine.dispatch(callbackQueryUpdate("cancel"))).isTrue();

            @SuppressWarnings({"unchecked", "rawtypes"})
            ArgumentCaptor<BotApiMethod> captor = ArgumentCaptor.forClass(BotApiMethod.class);
            verify(telegramClient, times(4)).execute(captor.capture());
            List<?> calls = captor.getAllValues();

            assertThat(calls.get(2)).isInstanceOf(AnswerCallbackQuery.class);
            assertThat(text(calls.get(3))).isEqualTo("Top up cancelled.");
        });
    }

    private static String text(Object botApiMethod) {
        assertThat(botApiMethod).isInstanceOf(SendMessage.class);
        return ((SendMessage) botApiMethod).getText();
    }

    private static Update messageUpdate(String text) {
        Chat chat = Chat.builder().id(CHAT_ID).type("private").build();
        Message message = new Message();
        message.setChat(chat);
        message.setText(text);

        Update update = new Update();
        update.setMessage(message);
        return update;
    }

    private static Update callbackQueryUpdate(String data) {
        Chat chat = Chat.builder().id(CHAT_ID).type("private").build();
        Message message = new Message();
        message.setChat(chat);

        CallbackQuery callbackQuery = new CallbackQuery();
        callbackQuery.setId("cb-1");
        callbackQuery.setData(data);
        callbackQuery.setMessage(message);

        Update update = new Update();
        update.setCallbackQuery(callbackQuery);
        return update;
    }

    @Configuration(proxyBeanMethods = false)
    static class MockTelegramClientConfig {

        @Bean
        TelegramClient telegramClient() {
            return mock(TelegramClient.class);
        }
    }
}
