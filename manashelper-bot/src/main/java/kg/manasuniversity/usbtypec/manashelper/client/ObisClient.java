package kg.manasuniversity.usbtypec.manashelper.client;

import kg.manasuniversity.usbtypec.manashelper.exception.ObisLoginException;
import kg.manasuniversity.usbtypec.manashelper.service.ObisSession;
import kg.manasuniversity.usbtypec.manashelper.service.ObisSessionManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

@Slf4j
@Service
@RequiredArgsConstructor
public class ObisClient {
    private static final String LOGIN_URL = "/site/login";
    private static final String ATTENDANCE_URL = "/vs-ders/taken-lessons";
    private static final String EXAMS_URL = "/vs-ders/taken-grades";

    private final ObisSessionManager sessionManager;

    public String fetchLoginPageHtml(Long chatId) {
        ObisSession session = sessionManager.getSession(chatId);

        return session.getClient()
            .get()
            .uri(LOGIN_URL)
            .retrieve()
            .body(String.class);
    }

    public void sendLoginRequest(
        Long chatId,
        String studentNumber,
        String plainPassword,
        String csrfToken
    ) {
        log.info("Sending login request: student number {}, password {}", studentNumber, plainPassword);
        ObisSession session = sessionManager.getSession(chatId);

        MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
        formData.add("LoginForm[username]", studentNumber);
        formData.add("LoginForm[password_hash]", plainPassword);
        formData.add("_csrf", csrfToken);

        String response = session.getClient()
            .post()
            .uri(LOGIN_URL)
            .contentType(MediaType.APPLICATION_FORM_URLENCODED)
            .body(formData)
            .retrieve()
            .body(String.class);

        if (response == null || response.contains(LOGIN_URL)) {
            throw new ObisLoginException("Login Failed");
        }
    }

    public String fetchAttendancePageHtml(Long chatId) {
        ObisSession session = sessionManager.getSession(chatId);

        return session.getClient()
            .get()
            .uri(ATTENDANCE_URL)
            .retrieve()
            .body(String.class);
    }

    public String fetchExamsPageHtml(Long chatId) {
        ObisSession session = sessionManager.getSession(chatId);

        return session.getClient()
            .get()
            .uri(EXAMS_URL)
            .retrieve()
            .body(String.class);
    }
}
