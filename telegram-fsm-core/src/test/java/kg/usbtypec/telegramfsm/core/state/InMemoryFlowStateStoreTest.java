package kg.usbtypec.telegramfsm.core.state;

import kg.usbtypec.telegramfsm.core.FlowState;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryFlowStateStoreTest {

    @Test
    void savesAndFindsState() {
        InMemoryFlowStateStore store = new InMemoryFlowStateStore(Duration.ofMinutes(30));
        FlowState state = new FlowState("topUpFlow", 1, Map.of("amount", 100));

        store.save(42L, state);

        assertThat(store.find(42L)).contains(state);
    }

    @Test
    void deleteRemovesState() {
        InMemoryFlowStateStore store = new InMemoryFlowStateStore(Duration.ofMinutes(30));
        store.save(42L, new FlowState("topUpFlow", 0, Map.of()));

        store.delete(42L);

        assertThat(store.find(42L)).isEmpty();
    }

    @Test
    void missingChatReturnsEmpty() {
        InMemoryFlowStateStore store = new InMemoryFlowStateStore(Duration.ofMinutes(30));

        assertThat(store.find(1L)).isEmpty();
    }

    @Test
    void expiresEntryAfterTtl() {
        MutableClock clock = new MutableClock(Instant.parse("2026-01-01T00:00:00Z"));
        InMemoryFlowStateStore store = new InMemoryFlowStateStore(Duration.ofMinutes(10), clock);
        store.save(42L, new FlowState("topUpFlow", 0, Map.of()));

        clock.advance(Duration.ofMinutes(11));

        assertThat(store.find(42L)).isEmpty();
    }

    @Test
    void doesNotExpireBeforeTtl() {
        MutableClock clock = new MutableClock(Instant.parse("2026-01-01T00:00:00Z"));
        InMemoryFlowStateStore store = new InMemoryFlowStateStore(Duration.ofMinutes(10), clock);
        store.save(42L, new FlowState("topUpFlow", 0, Map.of()));

        clock.advance(Duration.ofMinutes(5));

        assertThat(store.find(42L)).isPresent();
    }

    @Test
    void nullTtlNeverExpires() {
        MutableClock clock = new MutableClock(Instant.parse("2026-01-01T00:00:00Z"));
        InMemoryFlowStateStore store = new InMemoryFlowStateStore(null, clock);
        store.save(42L, new FlowState("topUpFlow", 0, Map.of()));

        clock.advance(Duration.ofDays(365));

        assertThat(store.find(42L)).isPresent();
    }

    private static final class MutableClock extends Clock {
        private Instant instant;

        private MutableClock(Instant instant) {
            this.instant = instant;
        }

        void advance(Duration duration) {
            instant = instant.plus(duration);
        }

        @Override
        public ZoneOffset getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(java.time.ZoneId zone) {
            throw new UnsupportedOperationException();
        }

        @Override
        public Instant instant() {
            return instant;
        }
    }
}
