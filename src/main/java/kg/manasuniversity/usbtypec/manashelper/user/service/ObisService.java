package kg.manasuniversity.usbtypec.manashelper.user.service;

import kg.manasuniversity.usbtypec.manashelper.user.model.LessonAttendance;
import kg.manasuniversity.usbtypec.manashelper.user.entity.User;
import kg.manasuniversity.usbtypec.manashelper.user.exception.ObisPageParserException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.model.LessonExams;
import kg.manasuniversity.usbtypec.manashelper.user.service.obis.parser.ObisParser;
import kg.manasuniversity.usbtypec.manashelper.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ObisService {
    private final ObisClient obisClient;
    private final ObisParser obisParser;
    private final UserRepository userRepository;
    private final CryptoService cryptoService;

    public void authenticate(Long userId, String studentNumber, String plainPassword) {
        String loginPageHtml = obisClient.fetchLoginPageHtml(userId);
        String csrf = obisParser.parseLoginPageCsrfToken(loginPageHtml);
        obisClient.sendLoginRequest(userId, studentNumber, plainPassword, csrf);
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

    public List<LessonAttendance> getUserAttendance(long userId)
        throws UserNotFoundException, ObisPageParserException {
        User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
        String studentNumber = getStudentNumber(user);
        String plainPassword = getPlainPassword(user);

        authenticate(userId, studentNumber, plainPassword);
        String attendancePageHtml = obisClient.fetchAttendancePageHtml(userId);

        return obisParser.parseLessonsAttendancePage(attendancePageHtml);
    }

    public List<LessonExams> getUserExamGrades(long userId)
        throws UserNotFoundException, ObisPageParserException {
        User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
        String studentNumber = getStudentNumber(user);
        String plainPassword = getPlainPassword(user);

        authenticate(userId, studentNumber, plainPassword);
        String attendancePageHtml = obisClient.fetchExamsPageHtml(userId);

        return obisParser.parseAttendanceHtmlPage(attendancePageHtml);
    }
}
