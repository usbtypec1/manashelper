package kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.mapper;

import kg.manasuniversity.usbtypec.manashelper.timetable.model.Dish;
import org.springframework.stereotype.Component;

@Component
public class DishMapper {
  public Dish mapEntityToModel(kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.entity.Dish entity) {
    return new Dish(
            entity.getName(),
            entity.getCalories(),
            entity.getPhotoUrl(),
            entity.getUpscaledPhotoUrl()
    );
  }
}
