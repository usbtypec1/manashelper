package kg.usbtypec.telegramfsm.spring.autoconfigure;

import kg.usbtypec.telegramfsm.core.Flow;
import kg.usbtypec.telegramfsm.core.engine.DefaultFlowManager;
import kg.usbtypec.telegramfsm.core.engine.FlowEngine;
import kg.usbtypec.telegramfsm.core.engine.FlowManager;
import kg.usbtypec.telegramfsm.core.engine.FlowRegistry;
import kg.usbtypec.telegramfsm.core.state.FlowStateStore;
import kg.usbtypec.telegramfsm.spring.FlowTrigger;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Bean;

import java.util.HashMap;
import java.util.Map;

/**
 * Wires up the core flow engine from every {@link Flow} bean in the application context, deriving each
 * flow's name from its bean name and picking up any {@link FlowTrigger} annotations on the {@code @Bean}
 * factory methods that produced them.
 */
@AutoConfiguration
@EnableConfigurationProperties(TelegramFsmProperties.class)
public class TelegramFsmAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public FlowRegistry flowRegistry(ApplicationContext applicationContext) {
        Map<String, Flow> flows = applicationContext.getBeansOfType(Flow.class);
        Map<String, String> triggers = new HashMap<>();
        for (String beanName : flows.keySet()) {
            FlowTrigger trigger = applicationContext.findAnnotationOnBean(beanName, FlowTrigger.class);
            if (trigger != null) {
                triggers.put(trigger.value(), beanName);
            }
        }
        return new FlowRegistry(flows, triggers);
    }

    @Bean
    @ConditionalOnMissingBean
    public FlowEngine flowEngine(FlowRegistry flowRegistry, FlowStateStore flowStateStore) {
        return new FlowEngine(flowRegistry, flowStateStore);
    }

    @Bean
    @ConditionalOnMissingBean
    public FlowManager flowManager(FlowRegistry flowRegistry, FlowStateStore flowStateStore) {
        return new DefaultFlowManager(flowRegistry, flowStateStore);
    }
}
