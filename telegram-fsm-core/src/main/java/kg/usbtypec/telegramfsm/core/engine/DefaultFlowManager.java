package kg.usbtypec.telegramfsm.core.engine;

import kg.usbtypec.telegramfsm.core.FlowState;
import kg.usbtypec.telegramfsm.core.state.FlowStateStore;

import java.util.HashMap;
import java.util.Map;

public final class DefaultFlowManager implements FlowManager {

    private final FlowRegistry registry;
    private final FlowStateStore stateStore;

    public DefaultFlowManager(FlowRegistry registry, FlowStateStore stateStore) {
        this.registry = registry;
        this.stateStore = stateStore;
    }

    @Override
    public void start(String flowName, long chatId) {
        start(flowName, chatId, Map.of());
    }

    @Override
    public void start(String flowName, long chatId, Map<String, Object> initialContext) {
        registry.require(flowName);
        stateStore.save(chatId, new FlowState(flowName, 0, new HashMap<>(initialContext)));
    }

    @Override
    public void cancel(long chatId) {
        stateStore.delete(chatId);
    }

    @Override
    public boolean isActive(long chatId) {
        return stateStore.find(chatId).isPresent();
    }
}
