package kg.manasuniversity.usbtypec.manashelper.user.service;

import kg.manasuniversity.usbtypec.manashelper.user.exception.ObisLoginException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.BodyInserters;

@Slf4j
@Service
@RequiredArgsConstructor
public class ObisClient {
    private final ObisSessionManager sessionManager;

    public String fetchLoginPageHtml(Long chatId) {
        ObisSession session = sessionManager.getSession(chatId);

        return session.getClient()
            .get()
            .uri("/site/login")
            .retrieve()
            .bodyToMono(String.class)
            .block();
    }

    public void sendLoginRequest(
        Long chatId,
        String studentNumber,
        String plainPassword,
        String csrfToken
    ) {
        ObisSession session = sessionManager.getSession(chatId);
        String response = session.getClient()
            .post()
            .uri("/site/login")
            .body(BodyInserters.fromFormData("LoginForm[username]", studentNumber)
                .with("LoginForm[password_hash]", plainPassword)
                .with("_csrf", csrfToken))
            .retrieve()
            .bodyToMono(String.class)
            .block();

        if (response == null || response.contains("/site/login")) {
            throw new ObisLoginException("Login Failed");
        }
    }

    public String fetchAttendancePageHtml(Long chatId) {
        ObisSession session = sessionManager.getSession(chatId);

        return session.getClient()
            .get()
            .uri("/vs-ders/taken-lessons")
            .retrieve()
            .bodyToMono(String.class)
            .block();
    }

    public String fetchExamsPageHtml(Long chatId) {
        ObisSession session = sessionManager.getSession(chatId);

        return session.getClient()
            .get()
            .uri("/vs-ders/taken-grades")
            .retrieve()
            .bodyToMono(String.class)
            .block();
    }
}