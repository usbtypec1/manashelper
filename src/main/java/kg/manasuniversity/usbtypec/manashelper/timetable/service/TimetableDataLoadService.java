package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Department;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.timetable.integration.initialdata.loader.TimetableDataLoader;
import kg.manasuniversity.usbtypec.manashelper.timetable.integration.initialdata.model.FacultyJsonDto;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.DepartmentRepository;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.FacultyRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.util.List;

@Service
public class TimetableDataLoadService {
  private static final Logger log = LoggerFactory.getLogger(TimetableDataLoadService.class);

  private final TimetableDataLoader timetableDataLoader;
  private final FacultyRepository facultyRepository;
  private final DepartmentRepository departmentRepository;
  private final CourseRepository courseRepository;

  public TimetableDataLoadService(
          TimetableDataLoader timetableDataLoader,
          FacultyRepository facultyRepository,
          DepartmentRepository departmentRepository,
          CourseRepository courseRepository
  ) {
    this.timetableDataLoader = timetableDataLoader;
    this.facultyRepository = facultyRepository;
    this.departmentRepository = departmentRepository;
    this.courseRepository = courseRepository;
  }

  public void loadInitialTimetableData() {
    List<FacultyJsonDto> faculties;
    try {
      faculties = timetableDataLoader.loadInitialData();
    } catch (IOException e) {
      log.error(e.getMessage());
      return;
    }

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
