package kg.manasuniversity.usbtypec.manashelper.scheduledtasks;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.entity.Dish;
import kg.manasuniversity.usbtypec.manashelper.repository.DailyMenuRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.DishRepository;
import kg.manasuniversity.usbtypec.manashelper.service.DailyMenuClient;
import kg.manasuniversity.usbtypec.manashelper.service.DailyMenuParser;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.Set;
import java.util.stream.Collectors;

@Component
public class SynchronizeDailyMenusTask {
  private static final Logger log = LoggerFactory.getLogger(SynchronizeDailyMenusTask.class);

  private final DailyMenuClient dailyMenuClient;
  private final DailyMenuParser dailyMenuParser;
  private final DishRepository dishRepository;
  private final DailyMenuRepository dailyMenuRepository;

  public SynchronizeDailyMenusTask(DailyMenuClient dailyMenuClient, DailyMenuParser dailyMenuParser, DishRepository dishRepository, DailyMenuRepository dailyMenuRepository) {
    this.dailyMenuClient = dailyMenuClient;
    this.dailyMenuParser = dailyMenuParser;
    this.dishRepository = dishRepository;
    this.dailyMenuRepository = dailyMenuRepository;
  }

  private static String norm(String s) {
    return s == null ? "" : s.trim().replaceAll("\\s+", " ").toLowerCase();
  }

  private static Set<String> toNameSetFromParsed(kg.manasuniversity.usbtypec.manashelper.model.DailyMenu parsed) {
    return parsed.dishes().stream()
            .map(d -> norm(d.name()))
            .collect(Collectors.toSet());
  }

  private static Set<String> toNameSetFromEntity(DailyMenu menu) {
    return menu.getDishes().stream()
            .map(d -> norm(d.getName()))
            .collect(Collectors.toSet());
  }

  @Scheduled(cron = "0 * * * * *")
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
