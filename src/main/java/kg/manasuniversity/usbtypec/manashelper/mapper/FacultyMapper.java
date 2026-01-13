package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.payload.response.FacultyResponse;
import org.springframework.stereotype.Component;

@Component
public class FacultyMapper {
  public FacultyResponse mapFacultyEntityToResponse(Faculty faculty) {
    return new FacultyResponse(faculty.getId(), faculty.getName());
  }
}
