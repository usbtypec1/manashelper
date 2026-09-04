package kg.usbtypec.telegramfsm.spring.autoconfigure;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.FlowBuilder;
import kg.usbtypec.telegramfsm.core.engine.FlowEngine;
import kg.usbtypec.telegramfsm.core.engine.FlowManager;
import kg.usbtypec.telegramfsm.core.engine.FlowRegistry;
import kg.usbtypec.telegramfsm.core.state.FlowStateStore;
import kg.usbtypec.telegramfsm.core.state.InMemoryFlowStateStore;
import kg.usbtypec.telegramfsm.spring.FlowTrigger;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.chat.Chat;
import org.telegram.telegrambots.meta.api.objects.message.Message;

import static org.assertj.core.api.Assertions.assertThat;

class TelegramFsmAutoConfigurationTest {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withConfiguration(AutoConfigurations.of(
                    TelegramFsmAutoConfiguration.class,
                    InMemoryStateStoreAutoConfiguration.class,
                    RedisStateStoreAutoConfiguration.class));

    @Test
    void defaultsToInMemoryStateStore() {
        contextRunner.run(context ->
                assertThat(context).getBean(FlowStateStore.class).isInstanceOf(InMemoryFlowStateStore.class));
    }

    @Test
    void wiresRegistryEngineAndManagerBeans() {
        contextRunner.withUserConfiguration(TopUpFlowConfig.class).run(context -> {
            assertThat(context).hasSingleBean(FlowRegistry.class);
            assertThat(context).hasSingleBean(FlowEngine.class);
            assertThat(context).hasSingleBean(FlowManager.class);
        });
    }

    @Test
    void flowTriggerStartsFlowOnMatchingCommand() {
        contextRunner.withUserConfiguration(TopUpFlowConfig.class).run(context -> {
            FlowEngine engine = context.getBean(FlowEngine.class);
            FlowStateStore stateStore = context.getBean(FlowStateStore.class);

            boolean handled = engine.dispatch(messageUpdate(7L, "/topup"));

            assertThat(handled).isTrue();
            assertThat(stateStore.find(7L)).isPresent();
        });
    }

    private static Update messageUpdate(long chatId, String text) {
        Chat chat = Chat.builder().id(chatId).type("private").build();
        Message message = new Message();
        message.setChat(chat);
        message.setText(text);
        Update update = new Update();
        update.setMessage(message);
        return update;
    }

    @Configuration(proxyBeanMethods = false)
    static class TopUpFlowConfig {

        @Bean
        @FlowTrigger("/topup")
        Flow topUpFlow() {
            return new FlowBuilder()
                    .startOnMessage((message, context) -> {
                    })
                    .nextOnMessage((message, context) -> {
                    })
                    .build();
        }
    }
}
