package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenuRating;
import kg.manasuniversity.usbtypec.manashelper.payload.response.DailyMenuRatingResponse;
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
