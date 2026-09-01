FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -q dependency:go-offline
COPY src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/target/recovery-backend-0.1.0.jar app.jar
# synthetic cases for the batch runner (copy of /data/cases.jsonl; regenerate
# both with data/generate.py if the dataset changes)
COPY data ./data
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
