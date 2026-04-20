ALTER TABLE daily_menu_ratings
    DROP COLUMN comment;

CREATE INDEX ix_dishes_name ON dishes (name);