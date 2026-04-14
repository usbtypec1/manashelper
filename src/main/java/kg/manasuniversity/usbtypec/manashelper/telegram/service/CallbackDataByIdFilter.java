package kg.manasuniversity.usbtypec.manashelper.telegram.service;

import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;

import java.util.Optional;
import java.util.UUID;

public class CallbackDataByIdFilter {
    public static String pack(CallbackData prefix, UUID id) {
        return prefix.name() + ":" + id;
    }

    public static String pack(CallbackData prefix, int id) {
        return prefix.name() + ":" + id;
    }

    public static Optional<UUID> parseUUID(CallbackData prefix, String callbackData) {
        String[] parts = callbackData.split(":");
        if (parts.length != 2) {
            return Optional.empty();
        }
        if (!prefix.name().equals(parts[0])) {
            return Optional.empty();
        }
        try {
            return Optional.of(UUID.fromString(parts[1]));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    public static Optional<Integer> parseInt(CallbackData prefix, String callbackData) {
        String[] parts = callbackData.split(":");
        if (parts.length != 2) {
            return Optional.empty();
        }
        if (!prefix.name().equals(parts[0])) {
            return Optional.empty();
        }
        try {
            return Optional.of(Integer.parseInt(parts[1]));
        } catch (NumberFormatException e) {
            return Optional.empty();
        }
    }
}
