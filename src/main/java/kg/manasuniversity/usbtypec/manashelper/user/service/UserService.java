package kg.manasuniversity.usbtypec.manashelper.user.service;

import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.model.UsersStatistics;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.util.function.Consumer;

@Service
public class UserService {
    private final UserRepository userRepository;
    private final CryptoService cryptoService;
    private final ObisService obisService;

    public UserService(UserRepository userRepository, CryptoService cryptoService, ObisService obisService) {
        this.userRepository = userRepository;
        this.cryptoService = cryptoService;
        this.obisService = obisService;
    }

    public void upsertUser(Long userId, String fullName, String username) {
        Consumer<User> onPresent = (user) -> {
            user.setFullName(fullName);
            user.setUsername(username);
            userRepository.save(user);
        };
        Runnable onMissing = () -> {
            User user = new User(userId, fullName, username);
            userRepository.save(user);
        };
        userRepository.findById(userId).ifPresentOrElse(onPresent, onMissing);
    }

    public void updateUserCredentials(
        Long userId,
        String studentNumber,
        String plainPassword
    ) throws UserNotFoundException {
        User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));

        obisService.authenticate(userId, studentNumber, plainPassword);

        String encryptedPassword = cryptoService.encrypt(plainPassword);
        user.setStudentNumber(studentNumber);
        user.setEncryptedPassword(encryptedPassword);
        userRepository.save(user);
    }

    public UsersStatistics getUsersStatistics() {
        long totalUsersCount = userRepository.count();
        long usersWithCredentialsCount = userRepository.countByStudentNumberIsNotNull();

        int usersWithCredentialsPercentage = totalUsersCount != 0
            ? (int) ((usersWithCredentialsCount * 100) / totalUsersCount) : 0;

        return new UsersStatistics(totalUsersCount, usersWithCredentialsCount, usersWithCredentialsPercentage);
    }
}
