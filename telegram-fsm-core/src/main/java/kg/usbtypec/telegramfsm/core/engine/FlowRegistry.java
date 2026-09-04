package kg.usbtypec.telegramfsm.core.engine;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.exception.FlowNotFoundException;

import java.util.Map;
import java.util.Optional;

/**
 * All known flows, keyed by name, plus an optional map of trigger text (e.g. a command like {@code /topup})
 * to the flow it starts.
 */
public final class FlowRegistry {

    private final Map<String, Flow> flowsByName;
    private final Map<String, String> flowNameByTrigger;

    public FlowRegistry(Map<String, Flow> flowsByName, Map<String, String> flowNameByTrigger) {
        this.flowsByName = Map.copyOf(flowsByName);
        this.flowNameByTrigger = Map.copyOf(flowNameByTrigger);
    }

    public Flow require(String flowName) {
        Flow flow = flowsByName.get(flowName);
        if (flow == null) {
            throw new FlowNotFoundException(flowName);
        }
        return flow;
    }

    public Optional<Flow> find(String flowName) {
        return Optional.ofNullable(flowsByName.get(flowName));
    }

    public Optional<String> flowNameForTrigger(String triggerText) {
        return Optional.ofNullable(flowNameByTrigger.get(triggerText));
    }
}
