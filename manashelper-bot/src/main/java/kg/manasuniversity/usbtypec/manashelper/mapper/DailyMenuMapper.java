package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.model.DailyMenuModel;
import org.mapstruct.InjectionStrategy;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;

@Mapper(componentModel = "spring", injectionStrategy = InjectionStrategy.CONSTRUCTOR, uses = DishMapper.class)
public interface DailyMenuMapper {

    @Mapping(target = "dishModels", source = "entity.dishes")
    @Mapping(target = "averageRatingScore", source = "averageRating")
    DailyMenuModel mapEntityToModel(DailyMenu entity, double averageRating, int ratingsCount);
}
