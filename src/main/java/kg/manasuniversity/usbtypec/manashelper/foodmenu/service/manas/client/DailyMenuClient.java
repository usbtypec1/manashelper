package kg.manasuniversity.usbtypec.manashelper.foodmenu.service.manas.client;

import io.netty.handler.ssl.SslContext;
import io.netty.handler.ssl.SslContextBuilder;
import io.netty.handler.ssl.util.InsecureTrustManagerFactory;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import javax.net.ssl.SSLException;

@Service
public class DailyMenuClient {

    private final WebClient webClient;

    public DailyMenuClient() {
        try {
            SslContext sslContext = SslContextBuilder
                .forClient()
                .trustManager(InsecureTrustManagerFactory.INSTANCE)
                .build();

            HttpClient httpClient = HttpClient.create()
                .secure(t -> t.sslContext(sslContext));

            webClient = WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .baseUrl("https://beslenme.manas.edu.kg/")
                .build();
        } catch (SSLException e) {
            throw new RuntimeException(e);
        }
    }

    public String fetchDailyMenuHtml() {
        return webClient.get()
            .uri("/menu")
            .retrieve()
            .bodyToMono(String.class)
            .block();
    }
}
