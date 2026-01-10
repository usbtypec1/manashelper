package kg.manasuniversity.usbtypec.manashelper.service;

import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

@Service
public class ObisClient {
  private final RestTemplate restTemplate;

  public ObisClient(RestTemplate restTemplate) {
    this.restTemplate = restTemplate;
  }

  public String fetchLoginPageHtml() {
    ResponseEntity<String> response = restTemplate
            .exchange("https://obistest.manas.edu.kg/site/login", HttpMethod.GET, null, String.class);
    return response.getBody();
  }

  public void sendLoginRequest(String studentNumber, String plainPassword, String csrfToken) {


    HttpHeaders headers = new HttpHeaders();
    headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

    MultiValueMap<String, String> formData = new LinkedMultiValueMap<>();
    formData.add("LoginForm[username]", studentNumber);
    // Even though the field is named password_hash, it expects the plain password
    formData.add("LoginForm[password_hash]", plainPassword);
    formData.add("_csrf", csrfToken);

    HttpEntity<MultiValueMap<String, String>> loginEntity = new HttpEntity<>(formData, headers);

    ResponseEntity<String> response = restTemplate
            .exchange("https://obistest.manas.edu.kg/site/login", HttpMethod.POST, loginEntity, String.class);
  }

  public String fetchAttendancePageHtml() {
    ResponseEntity<String> response = restTemplate
            .exchange("https://obistest.manas.edu.kg/vs-ders/taken-lessons", HttpMethod.GET, null, String.class);
    return response.getBody();
  }

  public String fetchExamsPageHtml() {
    ResponseEntity<String> response = restTemplate
            .exchange("https://obistest.manas.edu.kg/vs-ders/taken-grades", HttpMethod.GET, null, String.class);
    return response.getBody();
  }
}
