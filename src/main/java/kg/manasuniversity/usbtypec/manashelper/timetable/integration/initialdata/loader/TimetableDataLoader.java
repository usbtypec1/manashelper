package kg.manasuniversity.usbtypec.manashelper.timetable.integration.initialdata.loader;

import kg.manasuniversity.usbtypec.manashelper.timetable.integration.initialdata.model.FacultyJsonDto;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

@Service
public class TimetableDataLoader {
  private final ObjectMapper objectMapper;

  public TimetableDataLoader(ObjectMapper objectMapper) {
    this.objectMapper = objectMapper;
  }

  public List<FacultyJsonDto> loadInitialData() throws IOException {
    InputStream in = new ClassPathResource("faculties.json").getInputStream();
    return objectMapper.readValue(in, new TypeReference<>() {
    });
  }
}
