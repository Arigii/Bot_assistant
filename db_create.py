import os
from sqlite3 import connect

CHARACTERS = [
    "Элтон Джон",
    "Джимми Хендрикс",
    "Курт Кобейн"
]

GENRES = [
    "Джатра",
    "Рок-опера",
    "Музыкальный фильм",
    "Мюзикл"
]

SETTINGS = [
    "Киберпанк-клуб",
    "Плавающий город-концерт",
    "Лесной храм",
    "Космический поезд"
]


def insert_characters(characters: list[str]):
    conn = connect('db.db')
    cur = conn.cursor()
    for character in characters:
        check_character = cur.execute(f"select * from characters where name = '{character}'").fetchone()
        if check_character is None:
            cur.execute(f"insert into characters (name) values ('{character}')")
    conn.commit()
    conn.close()


def insert_genres(genres: list[str]):
    conn = connect('db.db')
    cur = conn.cursor()
    for genre in genres:
        check_genre = cur.execute(f"select * from genres where name = '{genre}'").fetchone()
        if check_genre is None:
            cur.execute(f"insert into genres (name) values ('{genre}')")
    conn.commit()
    conn.close()


def insert_settings(settings: list[str]):
    conn = connect('db.db')
    cur = conn.cursor()
    for setting in settings:
        check_character = cur.execute(f"select * from settings where name = '{setting}'").fetchone()
        if check_character is None:
            cur.execute(f"insert into settings (name) values ('{setting}')")
    conn.commit()
    conn.close()


def create_database():
    if not os.path.exists('db.db'):
        conn = connect('db.db')
        c = conn.cursor()

        c.execute('''CREATE TABLE characters (
        id   INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        name TEXT);''')

        c.execute('''CREATE TABLE genres (
        id   INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        name TEXT);''')

        c.execute('''CREATE TABLE settings (
                id   INTEGER PRIMARY KEY ASC AUTOINCREMENT,
                name TEXT);''')

        c.execute('''CREATE TABLE users (
        id         INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        chat_id    INTEGER UNIQUE,
        status     TEXT,
        request    TEXT,
        ai_history TEXT,
        tokens_left INTEGER,
        sessions_left INTEGER,
        genre_id   INTEGER REFERENCES genres (id),
        setting_id   INTEGER REFERENCES settings (id),
        character_id   INTEGER REFERENCES characters (id));''')
        conn.commit()
        conn.close()