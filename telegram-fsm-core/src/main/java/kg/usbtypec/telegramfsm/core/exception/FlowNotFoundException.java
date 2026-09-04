package kg.usbtypec.telegramfsm.core.exception;

public class FlowNotFoundException extends RuntimeException {

    public FlowNotFoundException(String flowName) {
        super("Flow not found: " + flowName);
    }
}
