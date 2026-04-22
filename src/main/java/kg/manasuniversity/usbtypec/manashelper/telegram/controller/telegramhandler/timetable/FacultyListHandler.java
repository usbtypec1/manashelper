package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.timetable;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.FacultyRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;

import static kg.manasuniversity.usbtypec.manashelper.telegram.service.UpdateFilters.isMessageTextEquals;

@Component
@RequiredArgsConstructor
public class FacultyListHandler implements TelegramUpdateHandler {
    private final FacultyRepository facultyRepository;
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        return isMessageTextEquals(update, "📅 Расписание") || isMessageTextEquals(update, "/timetable");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        List<Faculty> faculties = facultyRepository.findAll();

        List<InlineKeyboardRow> rows = faculties.stream()
            .map(this::toRow)
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        answerUtils.answerTextMessage(update, "Список факультетов", markup);
    }

    private InlineKeyboardRow toRow(Faculty faculty) {
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(faculty.getName())
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.FACULTY_DETAIL, faculty.getId()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
