package com.recovery;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class RecoveryApplication {

    public static void main(String[] args) {
        SpringApplication.run(RecoveryApplication.class, args);
    }
}
