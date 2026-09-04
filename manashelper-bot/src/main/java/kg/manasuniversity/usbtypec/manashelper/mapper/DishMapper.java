package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.model.DishModel;
import org.mapstruct.Mapper;

@Mapper(componentModel = "spring")
public interface DishMapper {
    DishModel toModel(Dish entity);
}
