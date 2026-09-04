package kg.manasuniversity.usbtypec.manashelper.service;

import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class ObisSessionManager {
    private final Map<Long, ObisSession> sessions;

    public ObisSessionManager() {
        this.sessions = new ConcurrentHashMap<>();
    }

    public ObisSession getSession(Long chatId) {
        return sessions.computeIfAbsent(chatId, id -> new ObisSession());
    }
}
