package kg.usbtypec.telegramfsm.spring.autoconfigure;

import com.fasterxml.jackson.databind.ObjectMapper;
import kg.usbtypec.telegramfsm.core.FlowState;
import kg.usbtypec.telegramfsm.core.state.FlowStateStore;
import kg.usbtypec.telegramfsm.spring.redis.RedisFlowStateStore;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.serializer.Jackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.StringRedisSerializer;

@AutoConfiguration
@EnableConfigurationProperties(TelegramFsmProperties.class)
@ConditionalOnClass(RedisConnectionFactory.class)
@ConditionalOnProperty(prefix = "telegram.fsm.state-store", name = "type", havingValue = "redis")
public class RedisStateStoreAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean(name = "telegramFsmRedisTemplate")
    public RedisTemplate<String, FlowState> telegramFsmRedisTemplate(
            RedisConnectionFactory connectionFactory, ObjectProvider<ObjectMapper> objectMapperProvider) {
        ObjectMapper objectMapper = objectMapperProvider.getIfAvailable(ObjectMapper::new).copy();

        RedisTemplate<String, FlowState> redisTemplate = new RedisTemplate<>();
        redisTemplate.setConnectionFactory(connectionFactory);
        redisTemplate.setKeySerializer(new StringRedisSerializer());
        redisTemplate.setValueSerializer(new Jackson2JsonRedisSerializer<>(objectMapper, FlowState.class));
        redisTemplate.afterPropertiesSet();
        return redisTemplate;
    }

    @Bean
    @ConditionalOnMissingBean(FlowStateStore.class)
    public FlowStateStore flowStateStore(
            RedisTemplate<String, FlowState> telegramFsmRedisTemplate, TelegramFsmProperties properties) {
        return new RedisFlowStateStore(
                telegramFsmRedisTemplate,
                properties.getStateStore().getRedis().getKeyPrefix(),
                properties.getStateStore().getTtl());
    }
}
