package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.model.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.model.Dish;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DailyMenuMapper {
    private final DishMapper dishMapper;

    public DailyMenu mapEntityToModel(
        kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu entity,
        double averageRating,
        int ratingsCount
    ) {
        List<Dish> dailyMenus = entity.getDishes().stream()
            .map(dishMapper::mapEntityToModel)
            .toList();
        return new DailyMenu(
            entity.getId(),
            dailyMenus,
            entity.getDate(),
            averageRating,
            ratingsCount,
            entity.getViewsCount()
        );
    }
}
