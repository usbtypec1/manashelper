package kg.manasuniversity.usbtypec.manashelper.foodmenu.mapper;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenuInfo;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.Dish;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
@RequiredArgsConstructor
public class DailyMenuMapper {
    private final DishMapper dishMapper;

    public DailyMenuInfo mapEntityToModel(
        DailyMenu entity,
        double averageRating,
        int ratingsCount,
        int viewsCount,
        int viewsCountForLastHour
    ) {
        List<Dish> dailyMenus = entity.getDishes().stream()
            .map(dishMapper::mapEntityToModel)
            .toList();
        return new DailyMenuInfo(
            entity.getId(),
            dailyMenus,
            entity.getDate(),
            averageRating,
            ratingsCount,
            viewsCount,
            viewsCountForLastHour
        );
    }
}
