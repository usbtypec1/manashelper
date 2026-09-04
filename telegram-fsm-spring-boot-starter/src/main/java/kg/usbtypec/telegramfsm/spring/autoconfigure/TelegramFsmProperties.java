package kg.usbtypec.telegramfsm.spring.autoconfigure;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.NestedConfigurationProperty;

import java.time.Duration;

@ConfigurationProperties(prefix = "telegram.fsm")
public class TelegramFsmProperties {

    @NestedConfigurationProperty
    private final StateStore stateStore = new StateStore();

    public StateStore getStateStore() {
        return stateStore;
    }

    public static class StateStore {

        /**
         * {@code in-memory} (default) or {@code redis}.
         */
        private String type = "in-memory";

        /**
         * How long an inactive flow is kept before it is dropped. {@code 0} or a negative duration disables
         * expiry.
         */
        private Duration ttl = Duration.ofMinutes(30);

        @NestedConfigurationProperty
        private final Redis redis = new Redis();

        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public Duration getTtl() {
            return ttl;
        }

        public void setTtl(Duration ttl) {
            this.ttl = ttl;
        }

        public Redis getRedis() {
            return redis;
        }

        public static class Redis {

            private String keyPrefix = "telegram:fsm:state:";

            public String getKeyPrefix() {
                return keyPrefix;
            }

            public void setKeyPrefix(String keyPrefix) {
                this.keyPrefix = keyPrefix;
            }
        }
    }
}
