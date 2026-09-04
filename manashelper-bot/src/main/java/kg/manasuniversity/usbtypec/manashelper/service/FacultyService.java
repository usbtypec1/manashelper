package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.mapper.FacultyMapper;
import kg.manasuniversity.usbtypec.manashelper.model.FacultyModel;
import kg.manasuniversity.usbtypec.manashelper.repository.FacultyRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class FacultyService {
    private final FacultyRepository facultyRepository;
    private final FacultyMapper facultyMapper;

    public List<FacultyModel> getAllFaculties() {
        return facultyRepository.findAll().stream()
            .map(facultyMapper::toModel)
            .toList();
    }
}
