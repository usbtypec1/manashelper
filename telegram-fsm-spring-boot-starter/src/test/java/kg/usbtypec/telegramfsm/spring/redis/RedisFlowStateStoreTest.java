package kg.usbtypec.telegramfsm.spring.redis;

import kg.usbtypec.telegramfsm.core.FlowState;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@SuppressWarnings("unchecked")
class RedisFlowStateStoreTest {

    private RedisTemplate<String, FlowState> redisTemplate;
    private ValueOperations<String, FlowState> valueOperations;
    private RedisFlowStateStore store;

    @BeforeEach
    void setUp() {
        redisTemplate = mock(RedisTemplate.class);
        valueOperations = mock(ValueOperations.class);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        store = new RedisFlowStateStore(redisTemplate, "telegram:fsm:state:", Duration.ofMinutes(30));
    }

    @Test
    void saveSetsValueWithPrefixedKeyAndTtl() {
        FlowState state = new FlowState("topUpFlow", 1, Map.of("amount", 100));

        store.save(42L, state);

        verify(valueOperations).set("telegram:fsm:state:42", state, Duration.ofMinutes(30));
    }

    @Test
    void saveWithoutTtlOmitsExpiry() {
        RedisFlowStateStore noTtlStore = new RedisFlowStateStore(redisTemplate, "telegram:fsm:state:", null);
        FlowState state = new FlowState("topUpFlow", 0, Map.of());

        noTtlStore.save(42L, state);

        verify(valueOperations).set("telegram:fsm:state:42", state);
    }

    @Test
    void findReadsByPrefixedKey() {
        FlowState state = new FlowState("topUpFlow", 2, Map.of());
        when(valueOperations.get("telegram:fsm:state:42")).thenReturn(state);

        assertThat(store.find(42L)).contains(state);
    }

    @Test
    void findReturnsEmptyWhenMissing() {
        when(valueOperations.get("telegram:fsm:state:42")).thenReturn(null);

        assertThat(store.find(42L)).isEmpty();
    }

    @Test
    void deleteRemovesByPrefixedKey() {
        store.delete(42L);

        verify(redisTemplate).delete("telegram:fsm:state:42");
    }
}
