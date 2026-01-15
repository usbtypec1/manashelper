package kg.manasuniversity.usbtypec.manashelper.telegram.integration.botapi.model;

public record TelegramSendMessageRequest(long chat_id, String text, String parse_mode) {
}
