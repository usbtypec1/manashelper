package kg.usbtypec.telegramfsm.core;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * Builds a linear {@link Flow}: each {@code next...} call appends a new step, and {@link #or} attaches
 * another handler - of any kind - to the step that was just added. When a step is reached, its handlers are
 * tried in the order they were added and the first one whose {@code matches(...)} accepts the update runs -
 * see {@link MessageHandler#matches} / {@link CallbackQueryHandler#matches}.
 *
 * <pre>{@code
 * new FlowBuilder()
 *         .startOnMessage(startHandler)
 *         .nextOnMessage(amountHandler)
 *         .nextOnCallbackQuery(confirmHandler)
 *         .or(onCallbackQuery(cancelHandler))
 *         .build();
 * }</pre>
 */
public final class FlowBuilder {

    private final List<FlowStep> steps = new ArrayList<>();

    public FlowBuilder startOnMessage(MessageHandler handler) {
        requireNoSteps();
        steps.add(FlowStep.of(new MessageStepHandler(Objects.requireNonNull(handler, "handler"))));
        return this;
    }

    public FlowBuilder startOnCallbackQuery(CallbackQueryHandler handler) {
        requireNoSteps();
        steps.add(FlowStep.of(new CallbackQueryStepHandler(Objects.requireNonNull(handler, "handler"))));
        return this;
    }

    public FlowBuilder nextOnMessage(MessageHandler handler) {
        requireAtLeastOneStep();
        steps.add(FlowStep.of(new MessageStepHandler(Objects.requireNonNull(handler, "handler"))));
        return this;
    }

    public FlowBuilder nextOnCallbackQuery(CallbackQueryHandler handler) {
        requireAtLeastOneStep();
        steps.add(FlowStep.of(new CallbackQueryStepHandler(Objects.requireNonNull(handler, "handler"))));
        return this;
    }

    /**
     * Attaches another handler to the step that was just added, so that step is tried against more than one
     * handler. Use the static {@link #onMessage} / {@link #onCallbackQuery} factory methods to build the
     * argument; there is no limit on how many handlers, or of which kind, a single step can have.
     */
    public FlowBuilder or(StepHandler additional) {
        requireAtLeastOneStep();
        int lastIndex = steps.size() - 1;
        steps.set(lastIndex, steps.get(lastIndex).withAdditional(Objects.requireNonNull(additional, "additional")));
        return this;
    }

    public static StepHandler onMessage(MessageHandler handler) {
        return new MessageStepHandler(Objects.requireNonNull(handler, "handler"));
    }

    public static StepHandler onCallbackQuery(CallbackQueryHandler handler) {
        return new CallbackQueryStepHandler(Objects.requireNonNull(handler, "handler"));
    }

    public Flow build() {
        requireAtLeastOneStep();
        return new Flow(List.copyOf(steps));
    }

    private void requireNoSteps() {
        if (!steps.isEmpty()) {
            throw new IllegalStateException("Flow already has a start step");
        }
    }

    private void requireAtLeastOneStep() {
        if (steps.isEmpty()) {
            throw new IllegalStateException("Flow must start with startOnMessage(...) or startOnCallbackQuery(...)");
        }
    }
}
