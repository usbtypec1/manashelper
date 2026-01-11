package kg.manasuniversity.usbtypec.manashelper.config;

import jakarta.transaction.Transactional;
import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.model.FacultyJsonDto;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.DepartmentRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.FacultyRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

import java.io.InputStream;
import java.util.List;

@Component
@Transactional
public class DataInitializer implements CommandLineRunner {
  private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);

  private final ObjectMapper objectMapper;

  private final FacultyRepository facultyRepository;
  private final DepartmentRepository departmentRepository;
  private final CourseRepository courseRepository;

  public DataInitializer(ObjectMapper objectMapper, FacultyRepository facultyRepository, DepartmentRepository departmentRepository, CourseRepository courseRepository) {
    this.objectMapper = objectMapper;
    this.facultyRepository = facultyRepository;
    this.departmentRepository = departmentRepository;
    this.courseRepository = courseRepository;
  }

  @Override
  public void run(String... args) throws Exception {
    InputStream in = new ClassPathResource("faculties.json").getInputStream();

    List<FacultyJsonDto> faculties = objectMapper.readValue(in, new TypeReference<>() {
    });

    for (FacultyJsonDto facultyDto : faculties) {
      var faculty = facultyRepository.save(new Faculty(facultyDto.id(), facultyDto.name()));
      for (var departmentDto : facultyDto.departments()) {
        var department = departmentRepository.save(new Department(departmentDto.id(), departmentDto.name(), faculty));
        for (var courseDto : departmentDto.courses()) {
          courseRepository.save(new Course(courseDto.id(), courseDto.number(), department));
        }
      }
    }

    log.info("Faculties loaded successfully");
  }
}
