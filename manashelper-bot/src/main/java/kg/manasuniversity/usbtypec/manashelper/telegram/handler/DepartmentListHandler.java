package kg.manasuniversity.usbtypec.manashelper.telegram.handler;

import kg.manasuniversity.usbtypec.manashelper.enums.CallbackData;
import kg.manasuniversity.usbtypec.manashelper.model.DepartmentSummary;
import kg.manasuniversity.usbtypec.manashelper.service.CallbackDataByIdFilter;
import kg.manasuniversity.usbtypec.manashelper.service.DepartmentService;
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
public class DepartmentListHandler extends TelegramUpdateHandler {
    private final DepartmentService departmentService;

    public DepartmentListHandler(TelegramClient telegramClient, DepartmentService departmentService) {
        super(telegramClient);
        this.departmentService = departmentService;
    }

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
        List<DepartmentSummary> departments = departmentService.getDepartmentsByFaculty(facultyId.get());
        List<InlineKeyboardRow> rows = departments.stream()
            .map(this::toRow)
            .toList();
        InlineKeyboardMarkup markup = new InlineKeyboardMarkup(rows);
        editTextMessage(update, "Список направлений", markup);

    }

    private InlineKeyboardRow toRow(DepartmentSummary department) {
        InlineKeyboardButton button = InlineKeyboardButton.builder()
            .text(department.name())
            .callbackData(CallbackDataByIdFilter.pack(CallbackData.DEPARTMENT_DETAIL, department.id()))
            .build();
        return new InlineKeyboardRow(button);
    }
}
