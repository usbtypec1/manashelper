package kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model;

import jakarta.annotation.Nullable;

public record TelegramSendMessageResponse(boolean ok, @Nullable String description) {
}
