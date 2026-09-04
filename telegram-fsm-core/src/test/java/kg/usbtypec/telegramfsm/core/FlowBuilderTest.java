package kg.usbtypec.telegramfsm.core;

import org.junit.jupiter.api.Test;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.chat.Chat;
import org.telegram.telegrambots.meta.api.objects.message.Message;

import java.util.Map;

import static kg.usbtypec.telegramfsm.core.FlowBuilder.onCallbackQuery;
import static kg.usbtypec.telegramfsm.core.FlowBuilder.onMessage;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FlowBuilderTest {

    private static final long CHAT_ID = 1L;

    private final MessageHandler noopMessageHandler = (message, context) -> {
    };
    private final CallbackQueryHandler noopCallbackHandler = (callbackQuery, context) -> {
    };

    @Test
    void buildsLinearFlowWithThreeSteps() {
        Flow flow = new FlowBuilder()
                .startOnMessage(noopMessageHandler)
                .nextOnMessage(noopMessageHandler)
                .nextOnCallbackQuery(noopCallbackHandler)
                .build();

        assertThat(flow.stepCount()).isEqualTo(3);
        assertThat(flow.step(0).firstMatching(messageUpdate("hi"), context())).isPresent();
        assertThat(flow.step(0).firstMatching(callbackQueryUpdate("data"), context())).isEmpty();
        assertThat(flow.step(2).firstMatching(callbackQueryUpdate("data"), context())).isPresent();
        assertThat(flow.step(2).firstMatching(messageUpdate("hi"), context())).isEmpty();
    }

    @Test
    void orAttachesAdditionalHandlerOfAnyKindToLastStep() {
        Flow flow = new FlowBuilder()
                .startOnMessage(noopMessageHandler)
                .nextOnMessage(noopMessageHandler)
                .or(onCallbackQuery(noopCallbackHandler))
                .build();

        FlowStep lastStep = flow.step(1);
        assertThat(lastStep.firstMatching(messageUpdate("hi"), context())).isPresent();
        assertThat(lastStep.firstMatching(callbackQueryUpdate("data"), context())).isPresent();
    }

    @Test
    void orAllowsSeveralHandlersOfTheSameKindEachWithItsOwnFilter() throws Exception {
        MessageHandler digitsHandler = new MessageHandler() {
            @Override
            public void handle(Message message, FlowContext context) {
                context.put("branch", "digits");
            }

            @Override
            public boolean matches(Message message, FlowContext context) {
                return message.getText().matches("\\d+");
            }
        };
        MessageHandler otherHandler = (message, context) -> context.put("branch", "other");

        Flow flow = new FlowBuilder()
                .startOnMessage(digitsHandler)
                .or(onMessage(otherHandler))
                .build();

        FlowContext digitsContext = context();
        flow.step(0).firstMatching(messageUpdate("123"), digitsContext).orElseThrow()
                .invoke(messageUpdate("123"), digitsContext);
        assertThat(digitsContext.<String>get("branch")).isEqualTo("digits");

        FlowContext otherContext = context();
        flow.step(0).firstMatching(messageUpdate("abc"), otherContext).orElseThrow()
                .invoke(messageUpdate("abc"), otherContext);
        assertThat(otherContext.<String>get("branch")).isEqualTo("other");
    }

    @Test
    void noHandlerMatchesWhenItsOwnFilterRejects() {
        MessageHandler yesOnlyHandler = new MessageHandler() {
            @Override
            public void handle(Message message, FlowContext context) {
            }

            @Override
            public boolean matches(Message message, FlowContext context) {
                return "yes".equals(message.getText());
            }
        };

        Flow flow = new FlowBuilder().startOnMessage(yesOnlyHandler).build();

        assertThat(flow.step(0).firstMatching(messageUpdate("no"), context())).isEmpty();
    }

    @Test
    void buildWithoutAnyStepThrows() {
        assertThatThrownBy(() -> new FlowBuilder().build())
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void startCalledTwiceThrows() {
        FlowBuilder builder = new FlowBuilder().startOnMessage(noopMessageHandler);

        assertThatThrownBy(() -> builder.startOnCallbackQuery(noopCallbackHandler))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void nextCalledBeforeStartThrows() {
        assertThatThrownBy(() -> new FlowBuilder().nextOnMessage(noopMessageHandler))
                .isInstanceOf(IllegalStateException.class);
    }

    private static FlowContext context() {
        return new FlowContext(new java.util.HashMap<>(Map.of()));
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
}
