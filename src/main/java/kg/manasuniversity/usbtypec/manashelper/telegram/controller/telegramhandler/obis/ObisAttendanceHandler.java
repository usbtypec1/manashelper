package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AttendanceFormatter;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.user.service.ObisService;
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
        List<LessonAttendance> attendanceResponseList = obisService.getUserAttendance(userId);

        String text = AttendanceFormatter.formatAttendance(
            attendanceResponseList.stream().map(AttendanceFormatter::computeLessonSkipOpportunities).toList()
        );
        answerTextMessage(update, text);
    }
}
