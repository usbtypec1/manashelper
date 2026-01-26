package kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.mapper;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.mapper.DishMapper;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.Dish;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class DailyMenuMapper {
  private final DishMapper dishMapper;

  public DailyMenuMapper(DishMapper dishMapper) {
    this.dishMapper = dishMapper;
  }

  public DailyMenu mapEntityToModel(
          kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.entity.DailyMenu entity,
          double averageRating,
          int ratingsCount,
          boolean hasComments
  ) {
    List<Dish> dailyMenus = entity.getDishes().stream()
            .map(dishMapper::mapEntityToModel)
            .toList();
    return new DailyMenu(entity.getId(), dailyMenus, entity.getDate(), averageRating, ratingsCount, hasComments, entity.getViewsCount());
  }
}
