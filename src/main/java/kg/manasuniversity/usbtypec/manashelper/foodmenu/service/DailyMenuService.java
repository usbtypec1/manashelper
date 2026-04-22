package kg.manasuniversity.usbtypec.manashelper.foodmenu.service;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenuView;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.mapper.DailyMenuMapper;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.model.FoodMenuRating;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DailyMenuRatingRepository;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DailyMenuRepository;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DailyMenuViewRepository;
import kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenuInfo;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class DailyMenuService {
    private static final ZoneId ZONE_ID = ZoneId.of("Asia/Bishkek");

    private final DailyMenuRepository dailyMenuRepository;
    private final DailyMenuMapper dailyMenuMapper;
    private final DailyMenuRatingRepository dailyMenuRatingRepository;
    private final UserRepository userRepository;
    private final DailyMenuViewRepository dailyMenuViewRepository;

    public DailyMenuInfo getDailyMenuBySkippingDays(int skipDays, Long userId) {
        ZonedDateTime now = ZonedDateTime.now(ZONE_ID);
        return getDailyMenuByDate(now.plusDays(skipDays).toLocalDate(), userId);
    }

    public DailyMenuInfo getDailyMenuByDate(LocalDate date, Long userId) {
        DailyMenu dailyMenu = dailyMenuRepository.findByDate(date)
            .orElseThrow(() -> new DailyMenuNotFoundException("Daily menu not found for date: " + date));

        List<DailyMenuRating> dailyMenuRatings = dailyMenuRatingRepository.findByDailyMenuIdWithUser(dailyMenu.getId());

        int ratingsCount = dailyMenuRatings.size();
        double averageRating = calculateAverageRating(dailyMenuRatings);

        createView(dailyMenu, userId);

        int viewsCount = dailyMenuViewRepository.countByMenuId(dailyMenu.getId());
        int viewsCountForLastHour = getViewsCountForLastHour(dailyMenu.getId());

        return dailyMenuMapper.mapEntityToModel(
            dailyMenu, averageRating, ratingsCount, viewsCount, viewsCountForLastHour);
    }

    public void setRating(Long userId, FoodMenuRating foodMenuRating) {
        Optional<DailyMenuRating> dailyMenuRating = dailyMenuRatingRepository
            .findByUserIdAndDailyMenuId(userId, foodMenuRating.dailyMenuId());

        if (dailyMenuRating.isEmpty()) {
            User userRef = userRepository.getReferenceById(userId);
            DailyMenu dailyMenuRef = dailyMenuRepository.getReferenceById(foodMenuRating.dailyMenuId());
            DailyMenuRating newDailyMenuRating = new DailyMenuRating(dailyMenuRef, userRef, foodMenuRating.rating());
            dailyMenuRatingRepository.save(newDailyMenuRating);
        } else {
            dailyMenuRating.get().setScore(foodMenuRating.rating());
        }
    }

    private int getViewsCountForLastHour(UUID dailyMenuId) {
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime oneHourAgo = now.minusHours(1);
        return dailyMenuViewRepository.countByMenuIdAndCreatedAtBetween(dailyMenuId, oneHourAgo, now);
    }

    private double calculateAverageRating(Collection<DailyMenuRating> dailyMenuRatings) {
        double averageRating = dailyMenuRatings.stream()
            .mapToInt(DailyMenuRating::getScore)
            .average()
            .orElse(0.0);
        return Math.round(averageRating * 100.0) / 100.0;
    }

    private void createView(DailyMenu dailyMenu, Long userId) {
        User user = userRepository.findById(userId).orElse(null);
        DailyMenuView view = new DailyMenuView(user, dailyMenu);
        dailyMenuViewRepository.save(view);
    }
}
