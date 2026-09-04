package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.model.DishModel;
import org.junit.jupiter.api.Test;
import org.mapstruct.factory.Mappers;

import static org.assertj.core.api.Assertions.assertThat;

class DishMapperTest {

    private final DishMapper dishMapper = Mappers.getMapper(DishMapper.class);

    @Test
    void toModel_shouldMapAllFields() {
        Dish dish = new Dish("Borsch", "https://example.com/photo.jpg", 350);

        DishModel model = dishMapper.toModel(dish);

        assertThat(model.name()).isEqualTo("Borsch");
        assertThat(model.calories()).isEqualTo(350);
        assertThat(model.photoUrl()).isEqualTo("https://example.com/photo.jpg");
        assertThat(model.upscaledPhotoUrl()).isNull();
    }

    @Test
    void toModel_shouldReturnNull_whenEntityIsNull() {
        assertThat(dishMapper.toModel(null)).isNull();
    }
}
