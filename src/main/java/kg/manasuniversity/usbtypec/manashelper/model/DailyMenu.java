package kg.manasuniversity.usbtypec.manashelper.model;

import java.time.LocalDate;
import java.util.List;

public record DailyMenu(
        List<Dish> dishes,
        LocalDate date
) {
}
