package kg.manasuniversity.usbtypec.manashelper.service;

import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.CookieManager;
import java.net.CookiePolicy;
import java.net.http.HttpClient;

public class ObisSession {

    private final RestClient restClient;

    public ObisSession() {
        CookieManager cookieManager = new CookieManager();
        cookieManager.setCookiePolicy(CookiePolicy.ACCEPT_ALL);

        HttpClient httpClient = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.ALWAYS)
            .cookieHandler(cookieManager)
            .build();

        this.restClient = RestClient.builder()
            .baseUrl("https://obistest.manas.edu.kg")
            .requestFactory(new JdkClientHttpRequestFactory(httpClient))
            .build();
    }

    public RestClient getClient() {
        return restClient;
    }
}
