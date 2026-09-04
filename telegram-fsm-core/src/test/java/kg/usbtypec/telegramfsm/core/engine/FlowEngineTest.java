package kg.usbtypec.telegramfsm.core.engine;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.FlowBuilder;
import kg.usbtypec.telegramfsm.core.RetryStepException;
import kg.usbtypec.telegramfsm.core.state.InMemoryFlowStateStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.chat.Chat;
import org.telegram.telegrambots.meta.api.objects.message.Message;

import java.time.Duration;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class FlowEngineTest {

    private static final long CHAT_ID = 100L;

    private InMemoryFlowStateStore stateStore;
    private FlowEngine engine;

    @BeforeEach
    void setUp() {
        Flow topUpFlow = new FlowBuilder()
                .startOnMessage((message, context) -> context.put("started", true))
                .nextOnMessage((message, context) -> {
                    int amount;
                    try {
                        amount = Integer.parseInt(message.getText());
                    } catch (NumberFormatException e) {
                        throw new RetryStepException("not a number");
                    }
                    context.put("amount", amount);
                })
                .nextOnCallbackQuery((callbackQuery, context) -> context.put("confirmed", true))
                .build();

        stateStore = new InMemoryFlowStateStore(Duration.ofMinutes(30));
        FlowRegistry registry = new FlowRegistry(Map.of("topUpFlow", topUpFlow), Map.of("/topup", "topUpFlow"));
        engine = new FlowEngine(registry, stateStore);
    }

    @Test
    void triggerMessageStartsFlowAndAdvancesToStepOne() {
        boolean handled = engine.dispatch(messageUpdate("/topup"));

        assertThat(handled).isTrue();
        assertThat(stateStore.find(CHAT_ID)).hasValueSatisfying(state -> {
            assertThat(state.flowName()).isEqualTo("topUpFlow");
            assertThat(state.stepIndex()).isEqualTo(1);
            assertThat(state.context()).containsEntry("started", true);
        });
    }

    @Test
    void unrelatedMessageIsNotHandledWhenNoFlowActive() {
        boolean handled = engine.dispatch(messageUpdate("hello"));

        assertThat(handled).isFalse();
        assertThat(stateStore.find(CHAT_ID)).isEmpty();
    }

    @Test
    void invalidInputRetriesSameStepWithoutAdvancing() {
        engine.dispatch(messageUpdate("/topup"));

        boolean handled = engine.dispatch(messageUpdate("not-a-number"));

        assertThat(handled).isTrue();
        assertThat(stateStore.find(CHAT_ID)).hasValueSatisfying(state ->
                assertThat(state.stepIndex()).isEqualTo(1));
    }

    @Test
    void fullFlowCompletesAndClearsState() {
        engine.dispatch(messageUpdate("/topup"));
        engine.dispatch(messageUpdate("250"));

        boolean handled = engine.dispatch(callbackQueryUpdate("confirm"));

        assertThat(handled).isTrue();
        assertThat(stateStore.find(CHAT_ID)).isEmpty();
    }

    @Test
    void contextIsSharedAcrossSteps() {
        engine.dispatch(messageUpdate("/topup"));
        engine.dispatch(messageUpdate("250"));

        assertThat(stateStore.find(CHAT_ID)).hasValueSatisfying(state -> {
            assertThat(state.context()).containsEntry("started", true);
            assertThat(state.context()).containsEntry("amount", 250);
        });
    }

    @Test
    void wrongUpdateKindForCurrentStepIsNotHandled() {
        engine.dispatch(messageUpdate("/topup"));
        engine.dispatch(messageUpdate("250"));

        boolean handled = engine.dispatch(messageUpdate("some text instead of a button press"));

        assertThat(handled).isFalse();
        assertThat(stateStore.find(CHAT_ID)).hasValueSatisfying(state ->
                assertThat(state.stepIndex()).isEqualTo(2));
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
        callbackQuery.setData(data);
        callbackQuery.setMessage(message);

        Update update = new Update();
        update.setCallbackQuery(callbackQuery);
        return update;
    }
}
