CREATE TABLE daily_menu_views
(
    id         UUID                        NOT NULL,
    user_id    BIGINT,
    menu_id    UUID                        NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT pk_daily_menu_views PRIMARY KEY (id)
);

ALTER TABLE daily_menu_views
    ADD CONSTRAINT FK_DAILY_MENU_VIEWS_ON_MENU FOREIGN KEY (menu_id) REFERENCES daily_menus (id);

ALTER TABLE daily_menu_views
    ADD CONSTRAINT FK_DAILY_MENU_VIEWS_ON_USER FOREIGN KEY (user_id) REFERENCES users (id);

ALTER TABLE daily_menus
    DROP COLUMN views_count;
