package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.model.Dish;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Component
public class DailyMenuMapper {
  private final DishMapper dishMapper;

  public DailyMenuMapper(DishMapper dishMapper) {
    this.dishMapper = dishMapper;
  }

  public DailyMenu mapEntityToModel(
          kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu entity,
          double averageRating,
          int ratingsCount,
          boolean hasComments
  ) {
    List<Dish> dailyMenus = entity.getDishes().stream()
            .map(dishMapper::mapEntityToModel)
            .toList();
    return new DailyMenu(entity.getId(), dailyMenus, entity.getDate(), averageRating, ratingsCount, hasComments);
  }
}
