package kg.manasuniversity.usbtypec.manashelper.service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class CookieStore {
    private final Map<String, String> cookies = new HashMap<>();

    public void addFromHeaders(List<String> setCookies) {
        if (setCookies == null) return;

        for (String cookie : setCookies) {
            String[] parts = cookie.split(";", 2)[0].split("=", 2);
            if (parts.length == 2) {
                cookies.put(parts[0], parts[1]);
            }
        }
    }

    public String buildCookieHeader() {
        return cookies.entrySet()
            .stream()
            .map(e -> e.getKey() + "=" + e.getValue())
            .collect(Collectors.joining("; "));
    }

    public boolean isEmpty() {
        return cookies.isEmpty();
    }
}
