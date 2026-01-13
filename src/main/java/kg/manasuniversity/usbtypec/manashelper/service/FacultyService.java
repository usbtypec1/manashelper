package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.mapper.FacultyMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.response.FacultyResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.FacultyRepository;
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
