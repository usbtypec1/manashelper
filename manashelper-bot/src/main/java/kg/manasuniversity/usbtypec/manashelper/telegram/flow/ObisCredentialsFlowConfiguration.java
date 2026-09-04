package kg.manasuniversity.usbtypec.manashelper.telegram.flow;

import kg.manasuniversity.usbtypec.manashelper.telegram.handler.ObisAcceptTermsStepHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.handler.ObisPasswordEnteredStepHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.handler.ObisStudentNumberEnteredStepHandler;
import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.FlowBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class ObisCredentialsFlowConfiguration {

    @Bean
    public Flow obisCredentialsFlow(
        ObisAcceptTermsStepHandler acceptTermsStepHandler,
        ObisStudentNumberEnteredStepHandler studentNumberEnteredStepHandler,
        ObisPasswordEnteredStepHandler passwordEnteredStepHandler
    ) {
        return new FlowBuilder()
            .startOnCallbackQuery(acceptTermsStepHandler)
            .nextOnMessage(studentNumberEnteredStepHandler)
            .nextOnMessage(passwordEnteredStepHandler)
            .build();
    }
}
