# Manashelper

## API documentation (OpenAPI)

This project exposes an OpenAPI schema and Swagger UI via Springdoc.

When the application is running:

- OpenAPI JSON: `http://localhost:${SERVER_PORT}/v3/api-docs`
- Swagger UI: `http://localhost:${SERVER_PORT}/swagger-ui/index.html`

If you are using a different base URL or port, replace `SERVER_PORT` accordingly.

## Quick start

1. Provide the required environment variables (see `src/main/resources/application.properties`).
2. Run the application (for example, `./mvnw spring-boot:run`).
3. Open the Swagger UI link above to browse the API.
