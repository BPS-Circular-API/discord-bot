-- This code creates the database and tables for /data/data.db
-- There are 5 tables

CREATE TABLE if not exists "dm_notify" (
	"user_id"	INT NOT NULL,
	"message"	TEXT DEFAULT 'A new Circular was just posted on the website!'
);

CREATE TABLE if not exists "guild_notify" (
	"guild_id"	INTEGER NOT NULL UNIQUE,
	"channel_id"	INTEGER UNIQUE,
	"message"	TEXT DEFAULT "There's a new circular up on the website!"
);

CREATE TABLE if not exists "logs" (
	"timestamp"	INTEGER NOT NULL,
	"log_level"	TEXT DEFAULT 'debug',
	"category"	TEXT,
	"msg"	TEXT
);

CREATE TABLE if not exists "suggestions" (
	"user_id"	INTEGER NOT NULL,
	"message_id"	INTEGER,
	"message"	TEXT
);

CREATE TABLE if not exists "search_feedback" (
	"user_id"	INTEGER,
	"message_id"	INTEGER,
	"search_query"	TEXT,
	"response"	TEXT
);
