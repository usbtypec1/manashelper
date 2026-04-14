package kg.manasuniversity.usbtypec.manashelper.foodmenu.service;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.mapper.DailyMenuMapper;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.model.FoodMenuRating;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DailyMenuRatingRepository;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.repository.DailyMenuRepository;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class DailyMenuService {
    private static final ZoneId ZONE_ID = ZoneId.of("Asia/Bishkek");

    private final DailyMenuRepository dailyMenuRepository;
    private final DailyMenuMapper dailyMenuMapper;
    private final DailyMenuRatingRepository dailyMenuRatingRepository;
    private final UserRepository userRepository;

    public kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenu getDailyMenuBySkippingDays(int skipDays) {
        ZonedDateTime now = ZonedDateTime.now(ZONE_ID);
        return getDailyMenuByDate(now.plusDays(skipDays).toLocalDate());
    }

    public kg.manasuniversity.usbtypec.manashelper.timetable.model.DailyMenu getDailyMenuByDate(LocalDate date) {
        DailyMenu dailyMenu = dailyMenuRepository.findByDate(date)
            .orElseThrow(() -> new DailyMenuNotFoundException("Daily menu not found for date: " + date));

        List<DailyMenuRating> dailyMenuRatings = dailyMenuRatingRepository.findByDailyMenuIdWithUser(dailyMenu.getId());

        int count = dailyMenuRatings.size();
        double avg = dailyMenuRatings.stream()
            .mapToInt(DailyMenuRating::getScore)
            .average()
            .orElse(0.0);
        dailyMenu.setViewsCount(dailyMenu.getViewsCount() + 1);
        dailyMenuRepository.save(dailyMenu);
        return dailyMenuMapper.mapEntityToModel(dailyMenu, avg, count);
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
}
