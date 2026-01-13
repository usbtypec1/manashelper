package kg.manasuniversity.usbtypec.manashelper.service.obis;

import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import kg.manasuniversity.usbtypec.manashelper.service.CryptoService;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public final class ObisService {
  private final ObisClient obisClient;
  private final ObisParser obisParser;
  private final UserRepository userRepository;
  private final CryptoService cryptoService;

  public ObisService(ObisClient obisClient, ObisParser obisParser, UserRepository userRepository, CryptoService cryptoService) {
    this.obisClient = obisClient;
    this.obisParser = obisParser;
    this.userRepository = userRepository;
    this.cryptoService = cryptoService;
  }

  public List<LessonAttendance> getUserAttendance(long userId) throws UserNotFoundException {
    User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));

    String studentNumber = user.getStudentNumber();
    String encryptedPassword = user.getEncryptedPassword();

    if (studentNumber == null || encryptedPassword == null) {
      throw new UserHasNoCredentialsException("User credentials are incomplete for id: " + userId);
    }

    String plainPassword = cryptoService.decrypt(encryptedPassword);

    String loginPageHtml = obisClient.fetchLoginPageHtml();
    String csrf = obisParser.parseLoginPageCsrfToken(loginPageHtml);
    obisClient.sendLoginRequest(studentNumber, plainPassword, csrf);
    String attendancePageHtml = obisClient.fetchAttendancePageHtml();
    return obisParser.parseLessonsAttendancePage(attendancePageHtml);
  }

  public List<LessonExams> getUserExamGrades(long userId) throws UserNotFoundException {
    User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
    String studentNumber = user.getStudentNumber();
    String encryptedPassword = user.getEncryptedPassword();

    if (studentNumber == null || encryptedPassword == null) {
      throw new UserHasNoCredentialsException("User credentials are incomplete for id: " + userId);
    }
    String plainPassword = cryptoService.decrypt(encryptedPassword);

    String loginPageHtml = obisClient.fetchLoginPageHtml();
    String csrf = obisParser.parseLoginPageCsrfToken(loginPageHtml);
    obisClient.sendLoginRequest(studentNumber, plainPassword, csrf);
    String attendancePageHtml = obisClient.fetchExamsPageHtml();
    return obisParser.parseTakenGradesPage(attendancePageHtml);
  }
}
