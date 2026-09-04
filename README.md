# Manashelper

## Functionality overview

Manashelper is a Spring Boot service that aggregates university data and exposes it over REST APIs. Core functionality includes:

- **Timetable lookup**: fetch course timetables and parse them into structured responses.
- **Faculty/department/course catalog**: list faculties, departments per faculty, and courses per department.
- **User tracking**: store and update which courses a user tracks for timetable updates.
- **Daily menu**: retrieve and parse cafeteria menu data.
- **Synchronization and notifications**: background tasks synchronize lessons and send pending Telegram messages.

These capabilities are implemented in the controller and service layers under
`manashelper-bot/src/main/java/kg/manasuniversity/usbtypec/manashelper`. This is a multi-module Maven project;
`manashelper-bot` is the Telegram bot module.

## API documentation (OpenAPI)

This project exposes an OpenAPI schema and Swagger UI via Springdoc.

When the application is running:

- OpenAPI JSON: `http://localhost:${SERVER_PORT}/v3/api-docs`
- Swagger UI: `http://localhost:${SERVER_PORT}/swagger-ui/index.html`

If you are using a different base URL or port, replace `SERVER_PORT` accordingly.

## Quick start

1. Provide the required environment variables (see `manashelper-bot/src/main/resources/application.yml`).
2. Run the application (for example, `mvn -pl manashelper-bot spring-boot:run`).
3. Open the Swagger UI link above to browse the API.
