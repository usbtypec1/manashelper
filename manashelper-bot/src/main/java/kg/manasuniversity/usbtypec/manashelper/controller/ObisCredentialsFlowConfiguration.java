package kg.manasuniversity.usbtypec.manashelper.controller;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.FlowBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The "accept terms -> submit credentials via web app" conversation started by {@link ObisCredentialsHandler}.
 * Unlike {@code telegram-fsm}'s trigger-by-message flows, this one is never reached through a registered
 * trigger text - {@link ObisCredentialsHandler} starts it explicitly via {@code FlowManager.start(...)} once
 * the user opens the OBIS credentials menu, so this bean carries no {@code @FlowTrigger}.
 */
@Configuration
public class ObisCredentialsFlowConfiguration {

    @Bean
    public Flow obisCredentialsFlow(
        ObisAcceptTermsStepHandler acceptTermsStepHandler,
        ObisCredentialsSubmittedStepHandler credentialsSubmittedStepHandler
    ) {
        return new FlowBuilder()
            .startOnCallbackQuery(acceptTermsStepHandler)
            .nextOnMessage(credentialsSubmittedStepHandler)
            .build();
    }
}
