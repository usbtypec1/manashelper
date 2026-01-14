package kg.manasuniversity.usbtypec.manashelper.service.food_menu;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.mapper.DailyMenuMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.request.RatingUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.repository.DailyMenuRatingRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.DailyMenuRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

@Service
public class DailyMenuService {
  private final DailyMenuRepository dailyMenuRepository;
  private final DailyMenuMapper dailyMenuMapper;
  private final DailyMenuRatingRepository dailyMenuRatingRepository;
  private final UserRepository userRepository;

  public DailyMenuService(
          DailyMenuRepository dailyMenuRepository,
          DailyMenuMapper dailyMenuMapper,
          DailyMenuRatingRepository dailyMenuRatingRepository,
          UserRepository userRepository
  ) {
    this.dailyMenuRepository = dailyMenuRepository;
    this.dailyMenuMapper = dailyMenuMapper;
    this.dailyMenuRatingRepository = dailyMenuRatingRepository;
    this.userRepository = userRepository;
  }

  public kg.manasuniversity.usbtypec.manashelper.model.DailyMenu getDailyMenuByDate(LocalDate date) {
    DailyMenu dailyMenu = dailyMenuRepository.findByDate(date)
            .orElseThrow(() -> new DailyMenuNotFoundException("Daily menu not found for date: " + date));

    List<DailyMenuRating> dailyMenuRatings = dailyMenuRatingRepository.findByDailyMenu(dailyMenu);

    int count = dailyMenuRatings.size();
    double avg = dailyMenuRatings.stream()
            .mapToInt(DailyMenuRating::getScore)
            .average()
            .orElse(0.0);

    return dailyMenuMapper.mapEntityToModel(dailyMenu, avg, count);
  }

  @Transactional
  public void updateDailyMenuRating(UUID dailyMenuId, RatingUpdateRequest requestBody) {
    if (!dailyMenuRepository.existsById(dailyMenuId)) {
      throw new DailyMenuNotFoundException("Daily menu not found with id: " + dailyMenuId);
    }
    if (!userRepository.existsById(requestBody.userId())) {
      throw new UserNotFoundException("User not found with id: " + requestBody.userId());
    }

    DailyMenu dailyMenu = dailyMenuRepository.getReferenceById(dailyMenuId);
    User user = userRepository.getReferenceById(requestBody.userId());

    DailyMenuRating rating = dailyMenuRatingRepository
            .findByDailyMenuAndUser(dailyMenu, user)
            .orElse(null);

    if (rating != null) {
      boolean sameScore = Objects.equals(rating.getScore(), requestBody.score());
      boolean sameComment = Objects.equals(rating.getComment(), requestBody.comment());

      if (sameScore && sameComment) {
        return;
      }
      rating.setScore(requestBody.score());
      rating.setComment(requestBody.comment());
      dailyMenuRatingRepository.save(rating);
    } else {
      rating = new DailyMenuRating(dailyMenu, user, requestBody.score(), requestBody.comment());
      dailyMenuRatingRepository.save(rating);
    }
  }
}
