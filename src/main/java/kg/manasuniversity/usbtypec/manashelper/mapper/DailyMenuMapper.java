package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.model.Dish;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class DailyMenuMapper {
  private final DishMapper dishMapper;

  public DailyMenuMapper(DishMapper dishMapper) {
    this.dishMapper = dishMapper;
  }

  public DailyMenu mapEntityToModel(kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu entity) {
    List<Dish> dailyMenus = entity.getDishes().stream()
            .map(dishMapper::mapEntityToModel)
            .toList();
    return new DailyMenu(dailyMenus, entity.getDate());
  }
}
