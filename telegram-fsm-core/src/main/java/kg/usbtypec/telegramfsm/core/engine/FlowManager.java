package kg.usbtypec.telegramfsm.core.engine;

import java.util.Map;

/**
 * Programmatic control over a chat's active flow, for starting a flow outside of a registered trigger
 * (e.g. from an inline keyboard button on a non-flow message) or cancelling one early.
 */
public interface FlowManager {

    void start(String flowName, long chatId);

    void start(String flowName, long chatId, Map<String, Object> initialContext);

    void cancel(long chatId);

    boolean isActive(long chatId);
}
