package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.timetable;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.FacultyRepository;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;

@Component
public class FacultyListHandler extends TelegramUpdateHandler {
    private final FacultyRepository facultyRepository;

    public FacultyListHandler(TelegramClient telegramClient, FacultyRepository facultyRepository) {
        super(telegramClient);
        this.facultyRepository = facultyRepository;
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            update.getMessage().getText().equals("📅 Расписание");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        List<Faculty> faculties = facultyRepository.findAll();

        List<InlineKeyboardRow> rows = faculties.stream()
            .map(this::toRow)
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        answerTextMessage(update, "Список факультетов", markup);
    }

    private InlineKeyboardRow toRow(Faculty faculty) {
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(faculty.getName())
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.FACULTY_DETAIL, faculty.getId()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
