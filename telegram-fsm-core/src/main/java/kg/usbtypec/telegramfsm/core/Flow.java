package kg.usbtypec.telegramfsm.core;

import java.util.List;

/**
 * An ordered sequence of {@link FlowStep}s sharing one {@link FlowContext}. Build one with {@link FlowBuilder}.
 */
public final class Flow {

    private final List<FlowStep> steps;

    Flow(List<FlowStep> steps) {
        this.steps = steps;
    }

    public FlowStep step(int index) {
        return steps.get(index);
    }

    public int stepCount() {
        return steps.size();
    }
}
