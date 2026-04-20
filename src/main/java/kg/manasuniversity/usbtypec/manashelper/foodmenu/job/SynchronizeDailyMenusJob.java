package kg.manasuniversity.usbtypec.manashelper.foodmenu.job;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DailyMenuRepository;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DishRepository;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.service.manas.client.DailyMenuClient;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.service.manas.parser.DailyMenuParser;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Set;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

@Service
@Slf4j
@RequiredArgsConstructor
public class SynchronizeDailyMenusJob {
    private final DailyMenuClient dailyMenuClient;
    private final DailyMenuParser dailyMenuParser;
    private final DishRepository dishRepository;
    private final DailyMenuRepository dailyMenuRepository;

    private static String norm(String s) {
        return s == null ? "" : s.trim().replaceAll("\\s+", " ").toLowerCase();
    }

    private static Set<String> toNameSetFromParsed(
        kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenu parsed) {
        return parsed.dishes().stream()
            .map(d -> norm(d.name()))
            .collect(Collectors.toSet());
    }

    private static Set<String> toNameSetFromEntity(DailyMenu menu) {
        return menu.getDishes().stream()
            .map(d -> norm(d.getName()))
            .collect(Collectors.toSet());
    }

    @Scheduled(fixedDelay = 10, timeUnit = TimeUnit.MINUTES)
    @Transactional
    public void synchronizeDailyMenus() {
        String html = dailyMenuClient.fetchDailyMenuHtml();
        var parsedMenus = dailyMenuParser.parse(html);

        for (var parsedMenu : parsedMenus) {
            DailyMenu menu = dailyMenuRepository
                .findByDate(parsedMenu.date())
                .orElseGet(() -> new DailyMenu(parsedMenu.date()));

            Set<String> newNames = toNameSetFromParsed(parsedMenu);
            Set<String> oldNames = menu.getId() == null
                ? Set.of()
                : toNameSetFromEntity(menu);

            if (newNames.equals(oldNames)) {
                continue;
            }

            log.info("Updating daily menu for date {}", parsedMenu.date());

            menu.clearDishes();
            for (var parsedDish : parsedMenu.dishes()) {
                String name = parsedDish.name();
                Dish dish = dishRepository.findByName(name)
                    .orElseGet(() -> dishRepository.save(
                        new Dish(name, parsedDish.photoUrl(), parsedDish.calories())
                    ));
                menu.addDish(dish);
            }
            dailyMenuRepository.save(menu);
        }
    }
}
