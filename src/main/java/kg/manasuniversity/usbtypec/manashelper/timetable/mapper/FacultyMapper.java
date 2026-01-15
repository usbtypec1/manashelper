package kg.manasuniversity.usbtypec.manashelper.timetable.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.FacultyResponse;
import org.springframework.stereotype.Component;

@Component
public class FacultyMapper {
  public FacultyResponse mapFacultyEntityToResponse(Faculty faculty) {
    return new FacultyResponse(faculty.getId(), faculty.getName());
  }
}
