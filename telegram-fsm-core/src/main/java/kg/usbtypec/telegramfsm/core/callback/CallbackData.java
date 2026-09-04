package kg.usbtypec.telegramfsm.core.callback;

import org.telegram.telegrambots.meta.api.objects.CallbackQuery;

import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * Builds and parses the {@code callback_data} of inline keyboard buttons, which Telegram only lets you carry
 * as a single string up to 64 bytes. Encodes it as {@code parts} joined by a separator (default {@code ":"}),
 * e.g. {@code "topup:confirm:150.00"}.
 *
 * <pre>{@code
 * // building a button's callback_data
 * InlineKeyboardButton.builder()
 *         .text("Confirm")
 *         .callbackData(CallbackData.join("confirm", amount))
 *         .build();
 *
 * // reading it back in a handler
 * CallbackData data = CallbackData.parse(callbackQuery);
 * if (data.hasPrefix("confirm")) {
 *     BigDecimal amount = data.partAsBigDecimal(1);
 * }
 * }</pre>
 */
public final class CallbackData {

    public static final String DEFAULT_SEPARATOR = ":";
    private static final int MAX_BYTES = 64;

    private final List<String> parts;

    private CallbackData(List<String> parts) {
        this.parts = parts;
    }

    public static CallbackData parse(CallbackQuery callbackQuery) {
        return parse(callbackQuery.getData());
    }

    public static CallbackData parse(String raw) {
        return parse(raw, DEFAULT_SEPARATOR);
    }

    public static CallbackData parse(CallbackQuery callbackQuery, String separator) {
        return parse(callbackQuery.getData(), separator);
    }

    public static CallbackData parse(String raw, String separator) {
        Objects.requireNonNull(separator, "separator");
        if (raw == null || raw.isEmpty()) {
            return new CallbackData(List.of());
        }
        return new CallbackData(List.of(raw.split(Pattern.quote(separator), -1)));
    }

    /**
     * Joins the parts with {@value #DEFAULT_SEPARATOR} into a string suitable for {@code callback_data}.
     *
     * @throws IllegalArgumentException if the result exceeds Telegram's 64-byte {@code callback_data} limit
     */
    public static String join(Object... parts) {
        return joinWithSeparator(DEFAULT_SEPARATOR, parts);
    }

    /**
     * Same as {@link #join(Object...)} but with a custom separator instead of {@value #DEFAULT_SEPARATOR}.
     * Named differently (rather than overloaded) on purpose: a {@code join(String, Object...)} overload next
     * to {@code join(Object...)} would make Java silently treat the first part as the separator on calls like
     * {@code join("topup", "confirm")}.
     */
    public static String joinWithSeparator(String separator, Object... parts) {
        Objects.requireNonNull(separator, "separator");
        String result = String.join(separator, stringify(parts));
        int byteLength = result.getBytes(StandardCharsets.UTF_8).length;
        if (byteLength > MAX_BYTES) {
            throw new IllegalArgumentException(
                    "callback_data '%s' is %d bytes, Telegram allows at most %d"
                            .formatted(result, byteLength, MAX_BYTES));
        }
        return result;
    }

    private static List<String> stringify(Object[] parts) {
        List<String> strings = new ArrayList<>(parts.length);
        for (Object part : parts) {
            strings.add(String.valueOf(part));
        }
        return strings;
    }

    public boolean hasPrefix(String prefix) {
        return !parts.isEmpty() && parts.get(0).equals(prefix);
    }

    public int size() {
        return parts.size();
    }

    public String part(int index) {
        if (index < 0 || index >= parts.size()) {
            throw new IndexOutOfBoundsException(
                    "No callback data part at index %d in %s".formatted(index, parts));
        }
        return parts.get(index);
    }

    public Optional<String> partOrEmpty(int index) {
        return index >= 0 && index < parts.size() ? Optional.of(parts.get(index)) : Optional.empty();
    }

    public int partAsInt(int index) {
        return Integer.parseInt(part(index));
    }

    public long partAsLong(int index) {
        return Long.parseLong(part(index));
    }

    public BigDecimal partAsBigDecimal(int index) {
        return new BigDecimal(part(index));
    }

    @Override
    public String toString() {
        return String.join(DEFAULT_SEPARATOR, parts);
    }
}
