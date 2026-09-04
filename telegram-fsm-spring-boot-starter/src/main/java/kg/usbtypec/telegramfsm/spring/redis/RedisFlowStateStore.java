package kg.usbtypec.telegramfsm.spring.redis;

import kg.usbtypec.telegramfsm.core.FlowState;
import kg.usbtypec.telegramfsm.core.state.FlowStateStore;
import org.springframework.data.redis.core.RedisTemplate;

import java.time.Duration;
import java.util.Objects;
import java.util.Optional;

/**
 * Stores flow state in Redis as JSON, so it is shared across all instances of the bot and survives restarts.
 * Context values must be simple JSON-serializable types (String, Number, Boolean, List, Map).
 */
public final class RedisFlowStateStore implements FlowStateStore {

    private final RedisTemplate<String, FlowState> redisTemplate;
    private final String keyPrefix;
    private final Duration ttl;

    public RedisFlowStateStore(RedisTemplate<String, FlowState> redisTemplate, String keyPrefix, Duration ttl) {
        this.redisTemplate = Objects.requireNonNull(redisTemplate, "redisTemplate");
        this.keyPrefix = Objects.requireNonNull(keyPrefix, "keyPrefix");
        this.ttl = ttl;
    }

    @Override
    public Optional<FlowState> find(long chatId) {
        return Optional.ofNullable(redisTemplate.opsForValue().get(key(chatId)));
    }

    @Override
    public void save(long chatId, FlowState state) {
        String key = key(chatId);
        if (ttl != null && !ttl.isZero() && !ttl.isNegative()) {
            redisTemplate.opsForValue().set(key, state, ttl);
        } else {
            redisTemplate.opsForValue().set(key, state);
        }
    }

    @Override
    public void delete(long chatId) {
        redisTemplate.delete(key(chatId));
    }

    private String key(long chatId) {
        return keyPrefix + chatId;
    }
}
