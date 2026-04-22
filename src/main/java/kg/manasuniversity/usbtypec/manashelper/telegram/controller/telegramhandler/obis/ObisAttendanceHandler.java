package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AttendanceFormatter;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.user.service.ObisService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isCallbackDataEquals;
import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isMessageTextEquals;
import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateUtils.getUserId;

@Slf4j
@Component
@RequiredArgsConstructor
public class ObisAttendanceHandler implements TelegramUpdateHandler {
    private final ObisService obisService;
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isCallbackDataEquals(update, "obis:attendance") || isMessageTextEquals(update, "/yoklama");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = getUserId(update);
        List<LessonAttendance> attendanceResponseList;
        try {
            attendanceResponseList = obisService.getUserAttendance(userId);
        } catch (UserHasNoCredentialsException e) {
            answerUtils.answerTextMessage(update, "Введите ваши данные от OBIS");
            return;
        }

        String text = AttendanceFormatter.formatAttendance(
            attendanceResponseList.stream().map(AttendanceFormatter::computeLessonSkipOpportunities).toList()
        );
        answerUtils.answerTextMessage(update, text);
    }
}
