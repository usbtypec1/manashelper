package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.CourseNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpdateCredentialsRequest;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
public class UserService {
  private final UserRepository userRepository;
  private final CryptoService cryptoService;
  private final CourseRepository courseRepository;

  public UserService(UserRepository userRepository, CryptoService cryptoService, CourseRepository courseRepository) {
    this.userRepository = userRepository;
    this.cryptoService = cryptoService;
    this.courseRepository = courseRepository;
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
    String encryptedPassword = cryptoService.encrypt(userRequest.plainPassword());
    user.setStudentNumber(userRequest.studentNumber());
    user.setEncryptedPassword(encryptedPassword);
    userRepository.save(user);
  }
}
