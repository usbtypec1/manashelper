package kg.manasuniversity.usbtypec.manashelper.shared.config;

import kg.manasuniversity.usbtypec.manashelper.user.service.CookieInterceptor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Scope;
import org.springframework.context.annotation.ScopedProxyMode;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.context.WebApplicationContext;

import java.io.IOException;
import java.util.Collections;

@Configuration
public class RestTemplateConfig {

  /**
   * Request-scoped cookie interceptor
   * New instance created for each HTTP request
   */
  @Bean
  @Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
  public CookieInterceptor cookieInterceptor() {
    return new CookieInterceptor();
  }

  @Bean
  @Scope(value = WebApplicationContext.SCOPE_REQUEST, proxyMode = ScopedProxyMode.TARGET_CLASS)
  public RestTemplate restTemplate(CookieInterceptor cookieInterceptor) {
    RestTemplate restTemplate = new RestTemplate();

    SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory() {
      @Override
      protected void prepareConnection(java.net.HttpURLConnection connection, String httpMethod)
              throws IOException {
        super.prepareConnection(connection, httpMethod);
        connection.setInstanceFollowRedirects(true);
      }
    };

    factory.setConnectTimeout(5000);
    factory.setReadTimeout(5000);
    restTemplate.setRequestFactory(factory);

    // Add cookie interceptor
    restTemplate.setInterceptors(Collections.singletonList(cookieInterceptor));

    return restTemplate;
  }

}