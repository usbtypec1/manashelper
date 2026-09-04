# ----------- Stage 1: Build -----------
FROM maven:3.9.9-eclipse-temurin-25 AS build

WORKDIR /app

COPY pom.xml checkstyle.xml ./
COPY manashelper-bot/pom.xml manashelper-bot/pom.xml
RUN mvn dependency:go-offline

COPY manashelper-bot/src manashelper-bot/src

RUN mvn clean verify


# ----------- Stage 2: Run -----------
FROM eclipse-temurin:25-jre-alpine

WORKDIR /app

COPY --from=build /app/manashelper-bot/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
