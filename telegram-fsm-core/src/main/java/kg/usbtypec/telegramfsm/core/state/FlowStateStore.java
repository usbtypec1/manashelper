package kg.usbtypec.telegramfsm.core.state;

import kg.usbtypec.telegramfsm.core.FlowState;

import java.util.Optional;

/**
 * Persists which flow/step/context a chat is currently in. Implementations: in-memory (default) or Redis.
 */
public interface FlowStateStore {

    Optional<FlowState> find(long chatId);

    void save(long chatId, FlowState state);

    void delete(long chatId);
}
