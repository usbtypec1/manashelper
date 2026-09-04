CREATE TABLE courses
(
    id            INTEGER NOT NULL,
    number        INTEGER NOT NULL,
    department_id UUID    NOT NULL,
    CONSTRAINT pk_courses PRIMARY KEY (id)
);

CREATE TABLE daily_menu_dishes
(
    dish_id UUID NOT NULL,
    menu_id UUID NOT NULL,
    CONSTRAINT pk_daily_menu_dishes PRIMARY KEY (dish_id, menu_id)
);

CREATE TABLE daily_menu_ratings
(
    id            UUID                        NOT NULL,
    daily_menu_id UUID                        NOT NULL,
    user_id       BIGINT                      NOT NULL,
    score         INTEGER                     NOT NULL,
    comment       VARCHAR(255),
    created_at    TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT pk_daily_menu_ratings PRIMARY KEY (id)
);

CREATE TABLE daily_menus
(
    id          UUID    NOT NULL,
    date        date    NOT NULL,
    views_count INTEGER NOT NULL,
    CONSTRAINT pk_daily_menus PRIMARY KEY (id)
);

CREATE TABLE departments
(
    id         UUID         NOT NULL,
    name       VARCHAR(128) NOT NULL,
    faculty_id UUID         NOT NULL,
    CONSTRAINT pk_departments PRIMARY KEY (id)
);

CREATE TABLE dishes
(
    id                 UUID                        NOT NULL,
    name               VARCHAR(255)                NOT NULL,
    photo_url          VARCHAR(255)                NOT NULL,
    calories           INTEGER                     NOT NULL,
    upscaled_photo_url VARCHAR(255),
    created_at         TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT pk_dishes PRIMARY KEY (id)
);

CREATE TABLE faculties
(
    id   UUID         NOT NULL,
    name VARCHAR(128) NOT NULL,
    CONSTRAINT pk_faculties PRIMARY KEY (id)
);

CREATE TABLE lessons
(
    id                 UUID                                      NOT NULL,
    synchronization_id UUID                                      NOT NULL,
    name               VARCHAR(128)                              NOT NULL,
    course_id          INTEGER                                   NOT NULL,
    teacher_name       VARCHAR(128)                              NOT NULL,
    location           VARCHAR(128)                              NOT NULL,
    starts_at          time WITHOUT TIME ZONE                    NOT NULL,
    ends_at            time WITHOUT TIME ZONE                    NOT NULL,
    weekday            INTEGER                                   NOT NULL,
    type               VARCHAR(255)                              NOT NULL,
    created_at         TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT pk_lessons PRIMARY KEY (id)
);

CREATE TABLE user_courses
(
    course_id INTEGER NOT NULL,
    user_id   BIGINT  NOT NULL,
    CONSTRAINT pk_user_courses PRIMARY KEY (course_id, user_id)
);

CREATE TABLE users
(
    id                                         BIGINT                      NOT NULL,
    full_name                                  VARCHAR(128)                NOT NULL,
    username                                   VARCHAR(128),
    student_number                             VARCHAR(64),
    encrypted_password                         VARCHAR(255),
    is_timetable_change_notifications_enabled  BOOLEAN                     NOT NULL,
    is_noon_food_menu_notifications_enabled    BOOLEAN                     NOT NULL,
    is_evening_food_menu_notifications_enabled BOOLEAN                     NOT NULL,
    created_at                                 TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    updated_at                                 TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id)
);

ALTER TABLE dishes
    ADD CONSTRAINT uc_dishes_name UNIQUE (name);

ALTER TABLE daily_menu_dishes
    ADD CONSTRAINT uk_daily_menu_dishes_menu_dish UNIQUE (menu_id, dish_id);

ALTER TABLE daily_menu_ratings
    ADD CONSTRAINT uk_menu_user UNIQUE (daily_menu_id, user_id);

CREATE INDEX idx_lessons_time ON lessons (starts_at, ends_at);

CREATE INDEX ix_dishes_name ON dishes (name);

ALTER TABLE courses
    ADD CONSTRAINT FK_COURSES_ON_DEPARTMENT FOREIGN KEY (department_id) REFERENCES departments (id);

ALTER TABLE daily_menu_ratings
    ADD CONSTRAINT FK_DAILY_MENU_RATINGS_ON_DAILY_MENU FOREIGN KEY (daily_menu_id) REFERENCES daily_menus (id);

ALTER TABLE daily_menu_ratings
    ADD CONSTRAINT FK_DAILY_MENU_RATINGS_ON_USER FOREIGN KEY (user_id) REFERENCES users (id);

ALTER TABLE departments
    ADD CONSTRAINT FK_DEPARTMENTS_ON_FACULTY FOREIGN KEY (faculty_id) REFERENCES faculties (id);

ALTER TABLE lessons
    ADD CONSTRAINT FK_LESSONS_ON_COURSE FOREIGN KEY (course_id) REFERENCES courses (id);

CREATE INDEX idx_lessons_course_id ON lessons (course_id);

ALTER TABLE daily_menu_dishes
    ADD CONSTRAINT fk_dailymenudish_on_daily_menu FOREIGN KEY (menu_id) REFERENCES daily_menus (id);

ALTER TABLE daily_menu_dishes
    ADD CONSTRAINT fk_dailymenudish_on_dish FOREIGN KEY (dish_id) REFERENCES dishes (id);

ALTER TABLE user_courses
    ADD CONSTRAINT fk_usercourse_on_course FOREIGN KEY (course_id) REFERENCES courses (id);

ALTER TABLE user_courses
    ADD CONSTRAINT fk_usercourse_on_user FOREIGN KEY (user_id) REFERENCES users (id);