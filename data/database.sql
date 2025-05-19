-- This code creates the database and tables for /data/data.db
-- There are 6 tables

CREATE TABLE IF NOT EXISTS "dm_notify" (
	"user_id"	INT NOT NULL,
	"message"	TEXT DEFAULT 'A new Circular was just posted on the website!'
);

CREATE TABLE IF NOT EXISTS "guild_notify" (
	"guild_id"	INTEGER NOT NULL UNIQUE,
	"channel_id"	INTEGER NOT NULL UNIQUE,
	"message"	TEXT DEFAULT "There's a new circular up on the website!"
);

CREATE TABLE IF NOT EXISTS "logs" (
	"timestamp"	INTEGER NOT NULL,
	"log_level"	TEXT NOT NULL DEFAULT 'debug',
	"category"	TEXT NOT NULL,
	"msg"	TEXT
);

CREATE TABLE IF NOT EXISTS "search_feedback" (
	"user_id"	INTEGER NOT NULL,
	"message_id"	INTEGER NOT NULL UNIQUE,
	"search_query"	TEXT NOT NULL,
	"response"	TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS "notif_msgs" (
    "timestamp" DATETIME DEFAULT NOW(),
	"circular_id"	INTEGER NOT NULL,
	"type"	TEXT NOT NULL,
	"msg_id"	INTEGER NOT NULL UNIQUE,
	"channel_id"	INTEGER,
	"guild_id"	INTEGER
);

CREATE TABLE IF NOT EXISTS "cache" (
	"title"	TEXT,
	"category"	TEXT,
	"data"	BLOB
);