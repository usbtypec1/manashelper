package kg.usbtypec.telegramfsm.core.engine;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.FlowContext;
import kg.usbtypec.telegramfsm.core.FlowState;
import kg.usbtypec.telegramfsm.core.FlowStep;
import kg.usbtypec.telegramfsm.core.RetryStepException;
import kg.usbtypec.telegramfsm.core.StepHandler;
import kg.usbtypec.telegramfsm.core.exception.FlowExecutionException;
import kg.usbtypec.telegramfsm.core.state.FlowStateStore;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

/**
 * Routes incoming Telegram updates to the step of the flow the chat currently sits in, advancing or
 * retrying the step and persisting the shared context after each dispatch.
 */
public final class FlowEngine {

    private final FlowRegistry registry;
    private final FlowStateStore stateStore;

    public FlowEngine(FlowRegistry registry, FlowStateStore stateStore) {
        this.registry = registry;
        this.stateStore = stateStore;
    }

    /**
     * @return {@code true} if the update was consumed by an active or newly triggered flow, {@code false}
     * if it should be handled by application code instead.
     */
    public boolean dispatch(Update update) {
        Long chatId = extractChatId(update);
        if (chatId == null) {
            return false;
        }

        Optional<FlowState> existing = stateStore.find(chatId);
        if (existing.isPresent()) {
            return handle(chatId, existing.get(), update);
        }

        if (update.hasMessage() && update.getMessage().hasText()) {
            Optional<String> flowName = registry.flowNameForTrigger(update.getMessage().getText());
            if (flowName.isPresent()) {
                return handle(chatId, new FlowState(flowName.get(), 0, new HashMap<>()), update);
            }
        }

        return false;
    }

    private boolean handle(long chatId, FlowState state, Update update) {
        Flow flow = registry.require(state.flowName());
        FlowStep step = flow.step(state.stepIndex());
        Map<String, Object> contextData = new HashMap<>(state.context());
        FlowContext context = new FlowContext(contextData);

        Optional<StepHandler> matched = step.firstMatching(update, context);
        if (matched.isEmpty()) {
            return false;
        }

        boolean retry = false;
        try {
            matched.get().invoke(update, context);
        } catch (RetryStepException e) {
            retry = true;
        } catch (TelegramApiException e) {
            throw new FlowExecutionException(
                    "Failed to execute step %d of flow '%s'".formatted(state.stepIndex(), state.flowName()), e);
        }

        if (retry) {
            stateStore.save(chatId, new FlowState(state.flowName(), state.stepIndex(), contextData));
            return true;
        }

        int nextStepIndex = state.stepIndex() + 1;
        if (nextStepIndex >= flow.stepCount()) {
            stateStore.delete(chatId);
        } else {
            stateStore.save(chatId, new FlowState(state.flowName(), nextStepIndex, contextData));
        }
        return true;
    }

    private Long extractChatId(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().getChatId();
        }
        if (update.hasCallbackQuery() && update.getCallbackQuery().getMessage() != null) {
            return update.getCallbackQuery().getMessage().getChatId();
        }
        return null;
    }
}
