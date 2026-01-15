package kg.manasuniversity.usbtypec.manashelper.timetable.service;

import kg.manasuniversity.usbtypec.manashelper.timetable.mapper.FacultyMapper;
import kg.manasuniversity.usbtypec.manashelper.timetable.dto.response.FacultyResponse;
import kg.manasuniversity.usbtypec.manashelper.timetable.repository.FacultyRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class FacultyService {
  private final FacultyRepository facultyRepository;
  private final FacultyMapper facultyMapper;

  public  FacultyService(FacultyRepository facultyRepository, FacultyMapper facultyMapper) {
    this.facultyRepository = facultyRepository;
    this.facultyMapper = facultyMapper;
  }

  public List<FacultyResponse> getAllFaculties() {
    return facultyRepository
            .findAll()
            .stream()
            .map(facultyMapper::mapFacultyEntityToResponse)
            .toList();
  }
}
