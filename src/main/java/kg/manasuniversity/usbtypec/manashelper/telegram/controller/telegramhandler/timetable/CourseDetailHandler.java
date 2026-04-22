package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.timetable;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class CourseDetailHandler implements TelegramUpdateHandler {
    private final CourseRepository courseRepository;
    private final UserRepository userRepository;
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        if (!update.hasCallbackQuery()) {
            return false;
        }
        String callbackData = update.getCallbackQuery().getData();
        return CallbackDataByIdFilter.parseInt(CallbackData.COURSE_DETAIL, callbackData).isPresent();
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        String callbackData = update.getCallbackQuery().getData();
        Optional<Integer> courseId = CallbackDataByIdFilter.parseInt(CallbackData.COURSE_DETAIL, callbackData);
        Optional<Course> course = courseRepository.findById(courseId.get());
        List<Course> courses = courseRepository.findAllByDepartmentId(course.get().getDepartment().getId());
        Optional<User> user = userRepository.findByIdWithCourses(update.getCallbackQuery().getFrom().getId());

        Set<Integer> courseIds = user.get().getCourses().stream().map(Course::getId).collect(Collectors.toSet());

        if (courseIds.contains(course.get().getId())) {
            courseIds.remove(course.get().getId());
            user.get().removeCourse(course.get());
        } else {
            courseIds.add(course.get().getId());
            user.get().addCourse(course.get());
        }
        userRepository.save(user.get());

        List<InlineKeyboardRow> rows = courses.stream()
            .map(c -> toRow(c, courseIds))
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        answerUtils.editTextMessage(update, "Список курсов", markup);
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
