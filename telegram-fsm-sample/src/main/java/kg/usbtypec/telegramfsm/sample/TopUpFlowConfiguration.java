package kg.usbtypec.telegramfsm.sample;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.FlowBuilder;
import kg.usbtypec.telegramfsm.spring.FlowTrigger;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import static kg.usbtypec.telegramfsm.core.FlowBuilder.onCallbackQuery;

@Configuration
public class TopUpFlowConfiguration {

    @Bean
    @FlowTrigger("/topup")
    public Flow topUpFlow(
            TopUpStartHandler startHandler,
            TopUpAmountHandler amountHandler,
            TopUpConfirmHandler confirmHandler,
            TopUpCancelHandler cancelHandler) {
        // Both handlers wait on the same step; each decides for itself (via matches(), based on the
        // callback_data prefix) whether it reacts to a given button press, so they are tried in order and
        // the first match wins.
        return new FlowBuilder()
                .startOnMessage(startHandler)
                .nextOnMessage(amountHandler)
                .nextOnCallbackQuery(confirmHandler)
                .or(onCallbackQuery(cancelHandler))
                .build();
    }
}
