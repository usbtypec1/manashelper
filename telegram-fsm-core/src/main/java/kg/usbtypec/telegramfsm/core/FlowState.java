package kg.usbtypec.telegramfsm.core;

import java.util.Map;

/**
 * Persisted state of one chat's running flow: which flow, which step, and the shared context data.
 */
public record FlowState(String flowName, int stepIndex, Map<String, Object> context) {
}
