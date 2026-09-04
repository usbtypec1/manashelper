package kg.usbtypec.telegramfsm.core;

import java.util.Map;
import java.util.Objects;

/**
 * Data shared between all steps of a single running {@link Flow} instance (i.e. for one chat).
 * Backed by a plain map so it can be persisted by any {@link kg.usbtypec.telegramfsm.core.state.FlowStateStore}.
 */
public final class FlowContext {

    private final Map<String, Object> data;

    public FlowContext(Map<String, Object> data) {
        this.data = Objects.requireNonNull(data, "data");
    }

    @SuppressWarnings("unchecked")
    public <T> T get(String key) {
        return (T) data.get(key);
    }

    @SuppressWarnings("unchecked")
    public <T> T get(String key, T defaultValue) {
        Object value = data.get(key);
        return value != null ? (T) value : defaultValue;
    }

    public void put(String key, Object value) {
        data.put(key, value);
    }

    public boolean contains(String key) {
        return data.containsKey(key);
    }

    public void remove(String key) {
        data.remove(key);
    }

    public Map<String, Object> asMap() {
        return data;
    }
}
