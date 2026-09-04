package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.enums.CallbackData;
import lombok.experimental.UtilityClass;

import java.util.Optional;
import java.util.UUID;

@UtilityClass
public class CallbackDataByIdFilter {

    public String pack(CallbackData prefix, UUID id) {
        return prefix.name() + ":" + id;
    }

    public String pack(CallbackData prefix, int id) {
        return prefix.name() + ":" + id;
    }

    public Optional<UUID> parseUUID(CallbackData prefix, String callbackData) {
        String[] parts = callbackData.split(":");
        if (parts.length != 2) {
            return Optional.empty();
        }
        if (!prefix.name().equals(parts[0])) {
            return Optional.empty();
        }
        try {
            return Optional.of(UUID.fromString(parts[1]));
        } catch (IllegalArgumentException _) {
            return Optional.empty();
        }
    }

    public Optional<Integer> parseInt(CallbackData prefix, String callbackData) {
        String[] parts = callbackData.split(":");
        if (parts.length != 2) {
            return Optional.empty();
        }
        if (!prefix.name().equals(parts[0])) {
            return Optional.empty();
        }
        try {
            return Optional.of(Integer.parseInt(parts[1]));
        } catch (NumberFormatException _) {
            return Optional.empty();
        }
    }
}
