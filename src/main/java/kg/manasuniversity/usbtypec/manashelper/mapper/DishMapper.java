package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.model.Dish;
import org.springframework.stereotype.Component;

@Component
public class DishMapper {
  public Dish mapEntityToModel(kg.manasuniversity.usbtypec.manashelper.entity.Dish entity) {
    return new Dish(
            entity.getName(),
            entity.getCalories(),
            entity.getPhotoUrl()
    );
  }
}
