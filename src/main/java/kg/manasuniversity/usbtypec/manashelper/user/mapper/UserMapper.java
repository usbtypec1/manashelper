package kg.manasuniversity.usbtypec.manashelper.user.mapper;

import kg.manasuniversity.usbtypec.manashelper.user.dto.response.UserGetResponse;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import org.springframework.stereotype.Service;

@Service
public class UserMapper {
  public UserGetResponse mapToUserGetResponse(User user) {
    return new UserGetResponse(
            user.getId(),
            user.getFullName(),
            user.getUsername(),
            user.getIsTimetableChangeNotificationsEnabled(),
            user.getIsNoonFoodMenuNotificationsEnabled(),
            user.getIsEveningFoodMenuNotificationsEnabled()
    );
  }
}
