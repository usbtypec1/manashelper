package kg.usbtypec.telegramfsm.core.state;

import kg.usbtypec.telegramfsm.core.FlowState;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Keeps flow state in a concurrent map. Fine for a single instance; state is lost on restart and not shared
 * across instances - use the Redis backed store for that.
 */
public final class InMemoryFlowStateStore implements FlowStateStore {

    private final Map<Long, Entry> states = new ConcurrentHashMap<>();
    private final Duration ttl;
    private final Clock clock;

    public InMemoryFlowStateStore(Duration ttl) {
        this(ttl, Clock.systemUTC());
    }

    public InMemoryFlowStateStore(Duration ttl, Clock clock) {
        this.ttl = ttl;
        this.clock = clock;
    }

    @Override
    public Optional<FlowState> find(long chatId) {
        Entry entry = states.get(chatId);
        if (entry == null) {
            return Optional.empty();
        }
        if (isExpired(entry)) {
            states.remove(chatId, entry);
            return Optional.empty();
        }
        return Optional.of(entry.state());
    }

    @Override
    public void save(long chatId, FlowState state) {
        states.put(chatId, new Entry(state, Instant.now(clock).plus(effectiveTtl())));
    }

    @Override
    public void delete(long chatId) {
        states.remove(chatId);
    }

    private boolean isExpired(Entry entry) {
        if (ttl == null || ttl.isZero() || ttl.isNegative()) {
            return false;
        }
        return Instant.now(clock).isAfter(entry.expiresAt());
    }

    private Duration effectiveTtl() {
        return ttl != null ? ttl : Duration.ZERO;
    }

    private record Entry(FlowState state, Instant expiresAt) {
    }
}
