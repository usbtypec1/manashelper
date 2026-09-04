package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.model.FacultySummary;
import kg.manasuniversity.usbtypec.manashelper.repository.FacultyRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class FacultyService {
    private final FacultyRepository facultyRepository;

    public List<FacultySummary> getAllFaculties() {
        return facultyRepository.findAll().stream()
            .map(this::toSummary)
            .toList();
    }

    private FacultySummary toSummary(Faculty faculty) {
        return new FacultySummary(faculty.getId(), faculty.getName());
    }
}
