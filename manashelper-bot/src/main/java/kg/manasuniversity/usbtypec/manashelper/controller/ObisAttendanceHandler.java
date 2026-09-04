package kg.manasuniversity.usbtypec.manashelper.controller;

import kg.manasuniversity.usbtypec.manashelper.service.AttendanceFormatter;
import kg.manasuniversity.usbtypec.manashelper.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.service.ObisService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;

@Slf4j
@Component
public class ObisAttendanceHandler extends TelegramUpdateHandler {
    private final ObisService obisService;

    public ObisAttendanceHandler(TelegramClient telegramClient, ObisService obisService) {
        super(telegramClient);
        this.obisService = obisService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals("obis:attendance");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = update.getCallbackQuery().getFrom().getId();
        List<LessonAttendance> attendanceResponseList;
        try {
            attendanceResponseList = obisService.getUserAttendance(userId);
        } catch (UserHasNoCredentialsException _) {
            answerTextMessage(update, "Введите ваши данные от OBIS");
            return;
        }

        String text = AttendanceFormatter.formatAttendance(
            attendanceResponseList.stream().map(AttendanceFormatter::computeLessonSkipOpportunities).toList()
        );
        answerTextMessage(update, text);
    }
}
