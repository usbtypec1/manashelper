package kg.usbtypec.telegramfsm.core;

import org.telegram.telegrambots.meta.api.objects.Update;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * One state of a {@link Flow}: an ordered list of {@link StepHandler}s, of any kind and each with its own
 * filter. The first handler whose filter matches the incoming update is the one that runs.
 */
public final class FlowStep {

    private final List<StepHandler> handlers;

    private FlowStep(List<StepHandler> handlers) {
        this.handlers = handlers;
    }

    static FlowStep of(StepHandler handler) {
        return new FlowStep(List.of(handler));
    }

    FlowStep withAdditional(StepHandler handler) {
        List<StepHandler> combined = new ArrayList<>(handlers);
        combined.add(handler);
        return new FlowStep(List.copyOf(combined));
    }

    public Optional<StepHandler> firstMatching(Update update, FlowContext context) {
        return handlers.stream().filter(handler -> handler.matches(update, context)).findFirst();
    }
}
