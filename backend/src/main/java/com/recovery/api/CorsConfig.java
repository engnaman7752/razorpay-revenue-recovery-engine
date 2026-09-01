package com.recovery.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** CORS for the dashboard dev server ONLY, and only on /api/**.
 * /internal/tools/** and /webhook/** get no CORS mapping at all. */
@Configuration
public class CorsConfig implements WebMvcConfigurer {

    @Value("${recovery.frontend-origin:http://localhost:5173}")
    private String frontendOrigin;

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(frontendOrigin)
                .allowedMethods("GET", "POST");
    }
}
