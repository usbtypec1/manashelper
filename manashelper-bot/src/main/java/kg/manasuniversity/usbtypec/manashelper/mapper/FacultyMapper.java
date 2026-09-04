package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Faculty;
import kg.manasuniversity.usbtypec.manashelper.model.FacultyModel;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface FacultyMapper {
    FacultyModel toModel(Faculty entity);
}
