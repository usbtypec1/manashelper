package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.timetable;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

@Component
public class CourseListHandler extends TelegramUpdateHandler {
    private final CourseRepository courseRepository;
    private final UserRepository userRepository;

    public CourseListHandler(TelegramClient telegramClient,
                             CourseRepository courseRepository,
                             UserRepository userRepository) {
        super(telegramClient);
        this.courseRepository = courseRepository;
        this.userRepository = userRepository;
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
        List<Course> courses = courseRepository.findAllByDepartmentId(departmentId.get());
        Optional<User> user = userRepository.findByIdWithCourses(update.getCallbackQuery().getFrom().getId());
        Set<Integer> courseIds = user.get().getCourses().stream().map(Course::getId).collect(Collectors.toSet());

        List<InlineKeyboardRow> rows = courses.stream()
            .map(course -> toRow(course, courseIds))
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        editTextMessage(update, "Список курсов", markup);
    }

    private InlineKeyboardRow toRow(Course course, Set<Integer> userCourseIds) {
        String textPrefix = userCourseIds.contains(course.getId()) ? "✅ " : "";
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(textPrefix + course.getNumber() + " курс")
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.COURSE_DETAIL, course.getId()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
