package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import kg.manasuniversity.usbtypec.manashelper.enums.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.model.CourseSummary;
import kg.manasuniversity.usbtypec.manashelper.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.service.CourseService;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
public class CourseListHandler extends TelegramUpdateHandler {
    private final CourseService courseService;

    public CourseListHandler(TelegramClient telegramClient, CourseService courseService) {
        super(telegramClient);
        this.courseService = courseService;
    }

    @Override
    public boolean shouldHandle(Update update) {
        if (!update.hasCallbackQuery()) {
            return false;
        }
        String callbackData = update.getCallbackQuery().getData();
        return CallbackDataByIdFilter.parseUUID(CallbackData.DEPARTMENT_DETAIL, callbackData).isPresent();
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        String callbackData = update.getCallbackQuery().getData();
        Optional<UUID> departmentId = CallbackDataByIdFilter.parseUUID(CallbackData.DEPARTMENT_DETAIL, callbackData);
        Long userId = update.getCallbackQuery().getFrom().getId();
        List<CourseSummary> courses = courseService.getCoursesByDepartment(departmentId.get(), userId);

        List<InlineKeyboardRow> rows = courses.stream()
            .map(this::toRow)
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        editTextMessage(update, "Список курсов", markup);
    }

    private InlineKeyboardRow toRow(CourseSummary course) {
        String textPrefix = course.isTracked() ? "✅ " : "";
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(textPrefix + course.number() + " курс")
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.COURSE_DETAIL, course.id()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
