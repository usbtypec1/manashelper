package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.model.DailyMenuModel;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.tuple;

class DailyMenuMapperTest {

    // DailyMenuMapper delegates to DishMapper via constructor injection, so unlike the other
    // mappers it can't be pulled from Mappers.getMapper() (that instantiates with a no-arg
    // constructor) — wire the generated impls directly instead.
    private final DailyMenuMapper dailyMenuMapper = new DailyMenuMapperImpl(new DishMapperImpl());

    @Test
    void mapEntityToModel_shouldMapAllFields() {
        DailyMenu entity = new DailyMenu(LocalDate.of(2026, 9, 4));
        entity.setViewsCount(42);
        entity.addDish(new Dish("Borsch", "https://example.com/photo.jpg", 350));

        DailyMenuModel model = dailyMenuMapper.mapEntityToModel(entity, 4.5, 10);

        assertThat(model.id()).isEqualTo(entity.getId());
        assertThat(model.date()).isEqualTo(LocalDate.of(2026, 9, 4));
        assertThat(model.averageRatingScore()).isEqualTo(4.5);
        assertThat(model.ratingsCount()).isEqualTo(10);
        assertThat(model.viewsCount()).isEqualTo(42);
        assertThat(model.dishModels())
            .extracting("name", "calories", "photoUrl")
            .containsExactly(tuple("Borsch", 350, "https://example.com/photo.jpg"));
    }

    @Test
    void mapEntityToModel_shouldReturnNull_whenEntityIsNull() {
        assertThat(dailyMenuMapper.mapEntityToModel(null, 0, 0)).isNull();
    }
}
