package kg.manasuniversity.usbtypec.manashelper.timetable.integration.initialdata.model;

import java.util.List;
import java.util.UUID;

public record FacultyJsonDto(
        UUID id,
        String name,
        List<DepartmentJsonDto> departments
) {
}
