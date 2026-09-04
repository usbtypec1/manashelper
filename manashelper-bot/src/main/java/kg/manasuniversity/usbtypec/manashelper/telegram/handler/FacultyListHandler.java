package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import kg.manasuniversity.usbtypec.manashelper.enums.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.model.FacultyModel;
import kg.manasuniversity.usbtypec.manashelper.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.service.FacultyService;
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
    private final FacultyService facultyService;

    public FacultyListHandler(TelegramClient telegramClient, FacultyService facultyService) {
        super(telegramClient);
        this.facultyService = facultyService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        return update.hasMessage() &&
            update.getMessage().hasText() &&
            update.getMessage().getText().equals("📅 Расписание");
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        List<FacultyModel> faculties = facultyService.getAllFaculties();

        List<InlineKeyboardRow> rows = faculties.stream()
            .map(this::toRow)
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        answerTextMessage(update, "Список факультетов", markup);
    }

    private InlineKeyboardRow toRow(FacultyModel faculty) {
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(faculty.name())
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.FACULTY_DETAIL, faculty.id()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
