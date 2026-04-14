package kg.manasuniversity.usbtypec.manashelper.user.service;

import io.netty.handler.codec.http.HttpHeaderNames;
import org.springframework.http.HttpHeaders;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.ClientRequest;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.ExchangeFunction;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import reactor.netty.http.client.HttpClient;

import java.util.ArrayList;
import java.util.List;

public class ObisSession {

    private final List<String> cookies = new ArrayList<>();

    private final WebClient webClient;

    public ObisSession() {

        HttpClient httpClient = HttpClient.create()
            .wiretap(true)
            .followRedirect(true, (previousHeaders, newRequest) -> {
                String prevCookie = previousHeaders.get(HttpHeaders.COOKIE);
                if (prevCookie != null) {
                    newRequest.header(HttpHeaders.COOKIE, prevCookie);
                }
                if (!cookies.isEmpty()) {
                    newRequest.header(HttpHeaders.COOKIE, String.join("; ", cookies));
                }
            })
            .doOnRedirect((response, connection) -> {
                List<String> setCookies = response.responseHeaders()
                    .getAll(HttpHeaderNames.SET_COOKIE);
                for (String raw : setCookies) {
                    cookies.add(raw.split(";", 2)[0]);
                }
            });
        this.webClient = WebClient.builder()
            .baseUrl("https://obistest.manas.edu.kg")
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .filter(this::cookieRequestFilter)
            .filter(this::cookieResponseFilter)
            .build();
    }

    private Mono<ClientResponse> cookieRequestFilter(ClientRequest request, ExchangeFunction next) {
        ClientRequest.Builder builder = ClientRequest.from(request);

        if (!cookies.isEmpty()) {
            builder.header(HttpHeaders.COOKIE, String.join("; ", cookies));
        }

        return next.exchange(builder.build());
    }

    private Mono<ClientResponse> cookieResponseFilter(ClientRequest request, ExchangeFunction next) {
        return next.exchange(request)
            .doOnNext(response -> {
                List<String> setCookies = response.headers().header(HttpHeaders.SET_COOKIE);

                for (String cookie : setCookies) {
                    cookies.add(cookie.split(";", 2)[0]);
                }
            });
    }

    public WebClient getClient() {
        return webClient;
    }
}