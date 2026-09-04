package kg.usbtypec.telegramfsm.spring;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Put on a {@code @Bean} method returning a {@code Flow} to automatically start that flow when a chat with
 * no active flow sends a message whose text equals {@link #value()} (e.g. a command like {@code /topup}).
 * That triggering message is then dispatched as the input to the flow's first step.
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface FlowTrigger {

    String value();
}
