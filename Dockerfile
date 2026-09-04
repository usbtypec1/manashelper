# ----------- Stage 1: Build -----------
FROM maven:3-eclipse-temurin-25-alpine AS build

WORKDIR /app

# Копируем pom-файлы всех модулей для эффективного кэширования зависимостей
COPY pom.xml ./
COPY telegram-fsm-core/pom.xml telegram-fsm-core/
COPY telegram-fsm-spring-boot-starter/pom.xml telegram-fsm-spring-boot-starter/
COPY manashelper-bot/pom.xml manashelper-bot/

RUN mvn dependency:go-offline -B

# Копируем исходные тексты
COPY telegram-fsm-core telegram-fsm-core
COPY telegram-fsm-spring-boot-starter telegram-fsm-spring-boot-starter
COPY manashelper-bot manashelper-bot

RUN mvn clean package -DskipTests

# ----------- Stage 2: Minimal Run -----------
FROM eclipse-temurin:25-jre-alpine

WORKDIR /app

# Копируем собранный jar-файл из стадии сборки
COPY --from=build /app/manashelper-bot/target/*.jar app.jar

# Запуск от root пользователя (по умолчанию в контейнере)
USER root

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
