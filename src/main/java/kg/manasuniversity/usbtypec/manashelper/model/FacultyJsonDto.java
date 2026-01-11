package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.List;
import java.util.UUID;

public record FacultyJsonDto(
        UUID id,
        String name,
        List<DepartmentJsonDto> departments
) {
}
