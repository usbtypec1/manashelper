package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import org.springframework.stereotype.Service;

@Service
public class UserService {
  private final UserRepository userRepository;
  private final CryptoService cryptoService;

  public UserService(UserRepository userRepository, CryptoService cryptoService) {
    this.userRepository = userRepository;
    this.cryptoService = cryptoService;
  }

  public void upsertUser(UserUpsertRequest userRequest)  {
    User user = new User(
            userRequest.id(),
            userRequest.studentNumber(),
            cryptoService.encrypt(userRequest.plainPassword())
    );
    userRepository.save(user);
//    String encryptedPassword = cryptoService.encrypt(userRequest.plainPassword());
//    userRepository.findById(userRequest.id()).ifPresentOrElse(user -> {
//      user.setStudentNumber(userRequest.studentNumber());
//      user.setEncryptedPassword(encryptedPassword);
//
//      userRepository.save(user);
//    }, () -> {
//      User user = new User(userRequest.id(), userRequest.studentNumber(), encryptedPassword);
//      userRepository.save(user);
//    });
  }
}
