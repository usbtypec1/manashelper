package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.ExamsFormatter;
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
        return update.hasCallbackQuery() && update.getCallbackQuery().getData().equals("obis:exams");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = update.getCallbackQuery().getFrom().getId();
        List<LessonExams> responses = obisService.getUserExamGrades(userId);
        String text = ExamsFormatter.format(responses);
        answerTextMessage(update, text);
    }
}
