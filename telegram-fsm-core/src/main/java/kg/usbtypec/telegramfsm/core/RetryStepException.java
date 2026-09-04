package kg.usbtypec.telegramfsm.core;

/**
 * Thrown by a {@link MessageHandler} or {@link CallbackQueryHandler} to signal that the received update was
 * invalid and the flow should stay on the current step (e.g. re-ask the user for input), instead of advancing
 * to the next one. Any context mutations made before throwing are still persisted.
 */
public class RetryStepException extends RuntimeException {

    public RetryStepException() {
        super();
    }

    public RetryStepException(String message) {
        super(message);
    }
}
