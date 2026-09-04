package kg.manasuniversity.usbtypec.manashelper.service;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpRequest;
import org.springframework.http.client.ClientHttpRequestExecution;
import org.springframework.http.client.ClientHttpRequestInterceptor;
import org.springframework.http.client.ClientHttpResponse;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

public class CookieInterceptor implements ClientHttpRequestInterceptor {
    private final List<String> cookies;

    public CookieInterceptor() {
        cookies = new ArrayList<>();
    }

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body,
                                        ClientHttpRequestExecution execution) throws IOException {
        if (!cookies.isEmpty()) {
            request.getHeaders().addAll(HttpHeaders.COOKIE, cookies);
        }

        ClientHttpResponse response = execution.execute(request, body);

        List<String> setCookieHeaders = response.getHeaders().get(HttpHeaders.SET_COOKIE);
        if (setCookieHeaders != null && !setCookieHeaders.isEmpty()) {
            cookies.clear();
            cookies.addAll(setCookieHeaders);
        }

        return response;
    }
}
