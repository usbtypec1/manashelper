package kg.manasuniversity.usbtypec.manashelper.service.food_menu;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.mapper.DailyMenuMapper;
import kg.manasuniversity.usbtypec.manashelper.mapper.DailyMenuRatingMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.request.RatingUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.payload.response.DailyMenuRatingResponse;
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
  private final DailyMenuRatingMapper dailyMenuRatingMapper;

  public DailyMenuService(
          DailyMenuRepository dailyMenuRepository,
          DailyMenuMapper dailyMenuMapper,
          DailyMenuRatingRepository dailyMenuRatingRepository,
          UserRepository userRepository,
          DailyMenuRatingMapper dailyMenuRatingMapper) {
    this.dailyMenuRepository = dailyMenuRepository;
    this.dailyMenuMapper = dailyMenuMapper;
    this.dailyMenuRatingRepository = dailyMenuRatingRepository;
    this.userRepository = userRepository;
    this.dailyMenuRatingMapper = dailyMenuRatingMapper;
  }

  public kg.manasuniversity.usbtypec.manashelper.model.DailyMenu getDailyMenuByDate(LocalDate date) {
    DailyMenu dailyMenu = dailyMenuRepository.findByDate(date)
            .orElseThrow(() -> new DailyMenuNotFoundException("Daily menu not found for date: " + date));

    List<DailyMenuRating> dailyMenuRatings = dailyMenuRatingRepository.findByDailyMenu_IdWithUser(dailyMenu.getId());

    int count = dailyMenuRatings.size();
    double avg = dailyMenuRatings.stream()
            .mapToInt(DailyMenuRating::getScore)
            .average()
            .orElse(0.0);
    boolean hasComments = dailyMenuRatings.stream()
            .anyMatch(rating -> rating.getComment() != null && !rating.getComment().isBlank());

    return dailyMenuMapper.mapEntityToModel(dailyMenu, avg, count, hasComments);
  }

  public List<DailyMenuRatingResponse> getDailyMenuRatings(UUID dailyMenuId, Long userId) {
    List<DailyMenuRating> ratings;
    if (userId == null) {
      ratings = dailyMenuRatingRepository.findByDailyMenu_IdWithUser(dailyMenuId);
    } else {
      ratings = dailyMenuRatingRepository.findByDailyMenu_IdAndUser_IdWithUser(dailyMenuId, userId);
    }
    return ratings.stream().map(dailyMenuRatingMapper::mapEntityToResponse).toList();
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
