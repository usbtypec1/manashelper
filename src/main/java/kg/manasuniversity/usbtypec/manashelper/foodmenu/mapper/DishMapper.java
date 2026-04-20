package kg.manasuniversity.usbtypec.manashelper.foodmenu.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.model.Dish;
import org.springframework.stereotype.Component;

@Component
public class DishMapper {
    public Dish mapEntityToModel(kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.Dish entity) {
        return new Dish(
            entity.getName(),
            entity.getCalories(),
            entity.getPhotoUrl(),
            entity.getUpscaledPhotoUrl()
        );
    }
}
