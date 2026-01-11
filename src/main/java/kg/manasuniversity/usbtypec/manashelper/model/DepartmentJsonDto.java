package kg.manasuniversity.usbtypec.manashelper.model;

import java.util.List;
import java.util.UUID;

public record DepartmentJsonDto(
        UUID id,
        String name,
        List<CourseJsonDto> courses
) {
}
