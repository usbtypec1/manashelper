package kg.usbtypec.telegramfsm.spring.autoconfigure;

import kg.usbtypec.telegramfsm.core.state.FlowStateStore;
import kg.usbtypec.telegramfsm.core.state.InMemoryFlowStateStore;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@EnableConfigurationProperties(TelegramFsmProperties.class)
@ConditionalOnProperty(
        prefix = "telegram.fsm.state-store",
        name = "type",
        havingValue = "in-memory",
        matchIfMissing = true)
public class InMemoryStateStoreAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean(FlowStateStore.class)
    public FlowStateStore flowStateStore(TelegramFsmProperties properties) {
        return new InMemoryFlowStateStore(properties.getStateStore().getTtl());
    }
}
