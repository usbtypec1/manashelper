package kg.usbtypec.telegramfsm.core.callback;

import org.junit.jupiter.api.Test;
import org.telegram.telegrambots.meta.api.objects.CallbackQuery;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CallbackDataTest {

    @Test
    void joinsPartsWithDefaultSeparator() {
        assertThat(CallbackData.join("topup", "confirm", 150)).isEqualTo("topup:confirm:150");
    }

    @Test
    void joinsPartsWithCustomSeparator() {
        assertThat(CallbackData.joinWithSeparator("|", "topup", "confirm")).isEqualTo("topup|confirm");
    }

    @Test
    void parsesRawStringIntoParts() {
        CallbackData data = CallbackData.parse("topup:confirm:150.00");

        assertThat(data.size()).isEqualTo(3);
        assertThat(data.part(0)).isEqualTo("topup");
        assertThat(data.part(1)).isEqualTo("confirm");
        assertThat(data.part(2)).isEqualTo("150.00");
    }

    @Test
    void parsesFromCallbackQuery() {
        CallbackQuery callbackQuery = new CallbackQuery();
        callbackQuery.setData("confirm:42");

        CallbackData data = CallbackData.parse(callbackQuery);

        assertThat(data.part(0)).isEqualTo("confirm");
        assertThat(data.partAsInt(1)).isEqualTo(42);
    }

    @Test
    void nullOrEmptyRawParsesToNoParts() {
        assertThat(CallbackData.parse((String) null).size()).isZero();
        assertThat(CallbackData.parse("").size()).isZero();
    }

    @Test
    void hasPrefixChecksFirstPart() {
        CallbackData data = CallbackData.parse("confirm:150.00");

        assertThat(data.hasPrefix("confirm")).isTrue();
        assertThat(data.hasPrefix("cancel")).isFalse();
    }

    @Test
    void hasPrefixOnEmptyDataIsFalse() {
        assertThat(CallbackData.parse("").hasPrefix("confirm")).isFalse();
    }

    @Test
    void typedAccessorsParseNumbers() {
        CallbackData data = CallbackData.parse("order:42:150.50");

        assertThat(data.partAsInt(1)).isEqualTo(42);
        assertThat(data.partAsLong(1)).isEqualTo(42L);
        assertThat(data.partAsBigDecimal(2)).isEqualByComparingTo(new BigDecimal("150.50"));
    }

    @Test
    void partOrEmptyIsEmptyPastTheEnd() {
        CallbackData data = CallbackData.parse("confirm");

        assertThat(data.partOrEmpty(0)).contains("confirm");
        assertThat(data.partOrEmpty(1)).isEmpty();
    }

    @Test
    void partOutOfRangeThrows() {
        CallbackData data = CallbackData.parse("confirm");

        assertThatThrownBy(() -> data.part(1)).isInstanceOf(IndexOutOfBoundsException.class);
    }

    @Test
    void joinRejectsPayloadOverTelegramsSixtyFourByteLimit() {
        String tooLong = "x".repeat(65);

        assertThatThrownBy(() -> CallbackData.join(tooLong))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("64");
    }

    @Test
    void roundTripsThroughJoinAndParse() {
        String raw = CallbackData.join("topup", "confirm", new BigDecimal("150.00"));

        CallbackData data = CallbackData.parse(raw);

        assertThat(data.hasPrefix("topup")).isTrue();
        assertThat(data.part(1)).isEqualTo("confirm");
        assertThat(data.partAsBigDecimal(2)).isEqualByComparingTo(new BigDecimal("150.00"));
    }
}
