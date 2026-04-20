package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.ExamsFormatter;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.user.service.ObisService;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;

@Component
public class ObisExamsHandler extends TelegramUpdateHandler {
    private final ObisService obisService;

    public ObisExamsHandler(TelegramClient telegramClient, ObisService obisService) {
        super(telegramClient);
        this.obisService = obisService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        if (update.hasMessage()) {
            return update.getMessage().hasText() && update.getMessage().getText().equals("/exams");
        } else if (update.hasCallbackQuery()) {
            return "obis:exams".equals(update.getCallbackQuery().getData());
        }
        return false;
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = getUserId(update);
        List<LessonExams> lessonExamsList;
        try {
            lessonExamsList = obisService.getUserExamGrades(userId);
        } catch (UserHasNoCredentialsException e) {
            answerTextMessage(update, "Введите ваши данные от OBIS");
            return;
        }
        String text = ExamsFormatter.format(lessonExamsList);
        answerTextMessage(update, text);
    }
}
