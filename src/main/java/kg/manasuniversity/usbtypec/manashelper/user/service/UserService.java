package kg.manasuniversity.usbtypec.manashelper.user.service;

import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpdateRequest;
import kg.manasuniversity.usbtypec.manashelper.user.dto.response.UserGetResponse;
import kg.manasuniversity.usbtypec.manashelper.user.dto.response.UsersStatisticsResponse;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpdateCredentialsRequest;
import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.user.mapper.UserMapper;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.util.function.Consumer;

@Service
public class UserService {
  private final UserRepository userRepository;
  private final CryptoService cryptoService;
  private final ObisService obisService;
  private final UserMapper userMapper;

  public UserService(UserRepository userRepository, CryptoService cryptoService, ObisService obisService, UserMapper userMapper) {
    this.userRepository = userRepository;
    this.cryptoService = cryptoService;
    this.obisService = obisService;
    this.userMapper = userMapper;
  }

  public void upsertUser(UserUpsertRequest userRequest) {
    Consumer<User> onPresent = (user) -> {
      user.setFullName(userRequest.fullName());
      user.setUsername(userRequest.username());
      userRepository.save(user);
    };
    Runnable onMissing = () -> {
      User user = new User(
              userRequest.id(),
              userRequest.fullName(),
              userRequest.username()
      );
      userRepository.save(user);
    };
    userRepository
            .findById(userRequest.id())
            .ifPresentOrElse(onPresent, onMissing);
  }

  public void updateUserCredentials(
          long userId,
          UserUpdateCredentialsRequest userRequest
  ) throws UserNotFoundException {
    User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));

    String studentNumber = userRequest.studentNumber();
    String plainPassword = userRequest.plainPassword();

    obisService.authenticate(studentNumber, plainPassword);

    String encryptedPassword = cryptoService.encrypt(userRequest.plainPassword());
    user.setStudentNumber(userRequest.studentNumber());
    user.setEncryptedPassword(encryptedPassword);
    userRepository.save(user);
  }

  public UsersStatisticsResponse getUsersStatistics() {
    int totalUsersCount = (int) userRepository.count();
    int usersWithCredentialsCount = userRepository.countByStudentNumberIsNotNullAndEncryptedPasswordIsNotNull();

    return new UsersStatisticsResponse(
            totalUsersCount,
            usersWithCredentialsCount
    );
  }

  public UserGetResponse getUserById(long id) throws UserNotFoundException {
    User user = userRepository
            .findById(id)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + id));
    return userMapper.mapToUserGetResponse(user);
  }

  public void updateUserById(long id, UserUpdateRequest requestData) {
    User user = userRepository
            .findById(id)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + id));

    user.setIsTimetableChangeNotificationsEnabled(requestData.isTimetableChangeNotificationsEnabled());
    user.setIsNoonFoodMenuNotificationsEnabled(requestData.isNoonFoodMenuNotificationsEnabled());
    user.setIsEveningFoodMenuNotificationsEnabled(requestData.isEveningFoodMenuNotificationsEnabled());

    userRepository.save(user);
  }
}
