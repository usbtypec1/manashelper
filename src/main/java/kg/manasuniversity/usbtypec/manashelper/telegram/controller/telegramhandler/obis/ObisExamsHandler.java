package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.obis;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.ExamsFormatter;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.user.service.ObisService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isCallbackDataEquals;
import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isMessageTextEquals;
import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateUtils.getUserId;

@Component
@RequiredArgsConstructor
public class ObisExamsHandler implements TelegramUpdateHandler {
    private final ObisService obisService;
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isCallbackDataEquals(update, "obis:exams") || isMessageTextEquals(update, "/exams");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        Long userId = getUserId(update);
        List<LessonExams> lessonExamsList;
        try {
            lessonExamsList = obisService.getUserExamGrades(userId);
        } catch (UserHasNoCredentialsException e) {
            answerUtils.answerTextMessage(update, "Введите ваши данные от OBIS");
            return;
        }
        String text = ExamsFormatter.format(lessonExamsList);
        answerUtils.answerTextMessage(update, text);
    }
}
