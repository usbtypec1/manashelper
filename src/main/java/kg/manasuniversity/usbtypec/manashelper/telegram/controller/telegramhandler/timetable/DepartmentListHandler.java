package kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.timetable;

import kg.manasuniversity.usbtypec.manashelper.telegram.controller.telegramhandler.TelegramUpdateHandler;
import kg.manasuniversity.usbtypec.manashelper.telegram.model.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.AnswerUtils;
import kg.manasuniversity.usbtypec.manashelper.telegram.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.DepartmentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class DepartmentListHandler implements TelegramUpdateHandler {
    private final DepartmentRepository departmentRepository;
    private final AnswerUtils answerUtils;

    @Override
    public boolean shouldHandle(Update update) {
        if (!update.hasCallbackQuery()) {
            return false;
        }
        String callbackData = update.getCallbackQuery().getData();
        return CallbackDataByIdFilter.parseUUID(CallbackData.FACULTY_DETAIL, callbackData).isPresent();
    }

    @Override
    public void handle(Update update) throws TelegramApiException {
        String callbackData = update.getCallbackQuery().getData();
        Optional<UUID> facultyId = CallbackDataByIdFilter.parseUUID(CallbackData.FACULTY_DETAIL, callbackData);
        List<Department> departments = departmentRepository.findAllByFacultyId(facultyId.get());
        List<InlineKeyboardRow> rows = departments.stream()
            .map(this::toRow)
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        answerUtils.editTextMessage(update, "Список направлений", markup);
    }

    private InlineKeyboardRow toRow(Department department) {
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(department.getName())
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.DEPARTMENT_DETAIL, department.getId()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
