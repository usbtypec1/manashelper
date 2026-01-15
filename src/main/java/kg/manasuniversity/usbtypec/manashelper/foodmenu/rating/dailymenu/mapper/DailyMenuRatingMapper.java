package kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.mapper;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.dto.response.DailyMenuRatingResponse;
import org.springframework.stereotype.Component;

@Component
public class DailyMenuRatingMapper {
  public DailyMenuRatingResponse mapEntityToResponse(
          DailyMenuRating dailyMenuRating
  ) {
    return new DailyMenuRatingResponse(
            dailyMenuRating.getUser().getId(),
            dailyMenuRating.getUser().getFullName(),
            dailyMenuRating.getScore(),
            dailyMenuRating.getComment()
    );
  }
}
