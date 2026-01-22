package kg.manasuniversity.usbtypec.manashelper.user.service;

import kg.manasuniversity.usbtypec.manashelper.user.dto.response.LessonAttendanceResponse;
import kg.manasuniversity.usbtypec.manashelper.user.dto.response.LessonExamsResponse;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.exception.ObisPageParserException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.client.ObisClient;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.parser.ObisParser;
import kg.manasuniversity.usbtypec.manashelper.user.mapper.LessonAttendanceMapper;
import kg.manasuniversity.usbtypec.manashelper.user.mapper.LessonExamsMapper;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public final class ObisService {
  private final ObisClient obisClient;
  private final ObisParser obisParser;
  private final UserRepository userRepository;
  private final CryptoService cryptoService;
  private final LessonAttendanceMapper lessonAttendanceMapper;
  private final LessonExamsMapper lessonExamsMapper;

  public ObisService(ObisClient obisClient, ObisParser obisParser, UserRepository userRepository, CryptoService cryptoService, LessonAttendanceMapper lessonAttendanceMapper, LessonExamsMapper lessonExamsMapper) {
    this.obisClient = obisClient;
    this.obisParser = obisParser;
    this.userRepository = userRepository;
    this.cryptoService = cryptoService;
    this.lessonAttendanceMapper = lessonAttendanceMapper;
    this.lessonExamsMapper = lessonExamsMapper;
  }

  public void authenticate(String studentNumber, String plainPassword) {
    String loginPageHtml = obisClient.fetchLoginPageHtml();
    String csrf = obisParser.parseLoginPageCsrfToken(loginPageHtml);
    obisClient.sendLoginRequest(studentNumber, plainPassword, csrf);
  }

  private String getStudentNumber(User user) throws UserHasNoCredentialsException {
    String studentNumber = user.getStudentNumber();
    if (studentNumber == null) {
      throw new UserHasNoCredentialsException("User credentials are incomplete for id: " + user.getId());
    }
    return studentNumber;
  }

  private String getPlainPassword(User user) throws UserHasNoCredentialsException {
    String encryptedPassword = user.getEncryptedPassword();
    if (encryptedPassword == null) {
      throw new UserHasNoCredentialsException("User credentials are incomplete for id: " + user.getId());
    }
    return cryptoService.decrypt(encryptedPassword);
  }

  public List<LessonAttendanceResponse> getUserAttendance(long userId) throws UserNotFoundException, ObisPageParserException {
    User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
    String studentNumber = getStudentNumber(user);
    String plainPassword = getPlainPassword(user);

    authenticate(studentNumber, plainPassword);
    String attendancePageHtml = obisClient.fetchAttendancePageHtml();

    List<LessonAttendance> lessonsAttendance = obisParser.parseLessonsAttendancePage(attendancePageHtml);
    return lessonsAttendance
            .stream()
            .map(lessonAttendanceMapper::mapToResponse)
            .toList();
  }

  public List<LessonExamsResponse> getUserExamGrades(long userId) throws UserNotFoundException, ObisPageParserException {
    User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
    String studentNumber = getStudentNumber(user);
    String plainPassword = getPlainPassword(user);

    authenticate(studentNumber, plainPassword);
    String attendancePageHtml = obisClient.fetchExamsPageHtml();

    List<LessonExams> lessonsExams = obisParser.parseAttendanceHtmlPage(attendancePageHtml);
    return lessonsExams
            .stream()
            .map(lessonExamsMapper::mapToResponse)
            .toList();
  }
}
