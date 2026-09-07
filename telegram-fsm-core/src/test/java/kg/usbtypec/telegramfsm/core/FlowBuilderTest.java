package kg.usbtypec.telegramfsm.core;

import org.junit.jupiter.api.Test;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.chat.Chat;
import org.telegram.telegrambots.meta.api.objects.message.Message;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.Map;

import static kg.usbtypec.telegramfsm.core.FlowBuilder.onCallbackQuery;
import static kg.usbtypec.telegramfsm.core.FlowBuilder.onMessage;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

class FlowBuilderTest {

    private static final long CHAT_ID = 1L;

    private final TelegramClient telegramClient = mock(TelegramClient.class);

    private final MessageHandler noopMessageHandler = context -> {
    };
    private final CallbackQueryHandler noopCallbackHandler = context -> {
    };

    @Test
    void buildsLinearFlowWithThreeSteps() {
        Flow flow = new FlowBuilder()
                .startOnMessage(noopMessageHandler)
                .nextOnMessage(noopMessageHandler)
                .nextOnCallbackQuery(noopCallbackHandler)
                .build();

        assertThat(flow.stepCount()).isEqualTo(3);
        assertThat(flow.step(0).firstMatching(messageUpdate("hi"), context(), telegramClient)).isPresent();
        assertThat(flow.step(0).firstMatching(callbackQueryUpdate("data"), context(), telegramClient)).isEmpty();
        assertThat(flow.step(2).firstMatching(callbackQueryUpdate("data"), context(), telegramClient)).isPresent();
        assertThat(flow.step(2).firstMatching(messageUpdate("hi"), context(), telegramClient)).isEmpty();
    }

    @Test
    void orAttachesAdditionalHandlerOfAnyKindToLastStep() {
        Flow flow = new FlowBuilder()
                .startOnMessage(noopMessageHandler)
                .nextOnMessage(noopMessageHandler)
                .or(onCallbackQuery(noopCallbackHandler))
                .build();

        FlowStep lastStep = flow.step(1);
        assertThat(lastStep.firstMatching(messageUpdate("hi"), context(), telegramClient)).isPresent();
        assertThat(lastStep.firstMatching(callbackQueryUpdate("data"), context(), telegramClient)).isPresent();
    }

    @Test
    void orAllowsSeveralHandlersOfTheSameKindEachWithItsOwnFilter() throws Exception {
        MessageHandler digitsHandler = new MessageHandler() {
            @Override
            public void handle(MessageContext context) {
                context.getFlowContext().put("branch", "digits");
            }

            @Override
            public boolean matches(MessageContext context) {
                return context.getText().matches("\\d+");
            }
        };
        MessageHandler otherHandler = context -> context.getFlowContext().put("branch", "other");

        Flow flow = new FlowBuilder()
                .startOnMessage(digitsHandler)
                .or(onMessage(otherHandler))
                .build();

        FlowContext digitsContext = context();
        flow.step(0).firstMatching(messageUpdate("123"), digitsContext, telegramClient).orElseThrow()
                .invoke(messageUpdate("123"), digitsContext, telegramClient);
        assertThat(digitsContext.<String>get("branch")).isEqualTo("digits");

        FlowContext otherContext = context();
        flow.step(0).firstMatching(messageUpdate("abc"), otherContext, telegramClient).orElseThrow()
                .invoke(messageUpdate("abc"), otherContext, telegramClient);
        assertThat(otherContext.<String>get("branch")).isEqualTo("other");
    }

    @Test
    void noHandlerMatchesWhenItsOwnFilterRejects() {
        MessageHandler yesOnlyHandler = new MessageHandler() {
            @Override
            public void handle(MessageContext context) {
            }

            @Override
            public boolean matches(MessageContext context) {
                return "yes".equals(context.getText());
            }
        };

        Flow flow = new FlowBuilder().startOnMessage(yesOnlyHandler).build();

        assertThat(flow.step(0).firstMatching(messageUpdate("no"), context(), telegramClient)).isEmpty();
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
