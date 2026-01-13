package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpdateCredentialsRequest;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import kg.manasuniversity.usbtypec.manashelper.service.obis.ObisClient;
import kg.manasuniversity.usbtypec.manashelper.service.obis.ObisService;
import org.springframework.stereotype.Service;

@Service
public class UserService {
  private final UserRepository userRepository;
  private final CryptoService cryptoService;
  private final ObisService obisService;
  private final ObisClient obisClient;

  public UserService(UserRepository userRepository, CryptoService cryptoService, ObisService obisService, ObisClient obisClient) {
    this.userRepository = userRepository;
    this.cryptoService = cryptoService;
    this.obisService = obisService;
    this.obisClient = obisClient;
  }

  public void upsertUser(UserUpsertRequest userRequest) {
    User user = new User(
            userRequest.id(),
            userRequest.fullName(),
            userRequest.username()
    );
    userRepository.save(user);
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
}
