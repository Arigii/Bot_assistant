import os
from sqlite3 import connect

LEVELS = [
    "Для музыканта",
    "Для слушателя",
]

GENRES = [
    "Реп",
    "Блюз",
    "Хип-хоп",
    "Джаз",
    "Металл"
]


def insert_levels(levels: list[str]):
    conn = connect('db.db')
    cur = conn.cursor()
    for level in levels:
        check_level = cur.execute(f"select * from levels where name = '{level}'").fetchone()
        if check_level is None:
            cur.execute(f"insert into levels (name) values ('{level}')")
    conn.commit()
    conn.close()


def insert_genres(genres: list[str]):
    conn = connect('db.db')
    cur = conn.cursor()
    for genre in genres:
        check_genre = cur.execute(f"select * from levels where name = '{genre}'").fetchone()
        if check_genre is None:
            cur.execute(f"insert into genres (name) values ('{genre}')")
    conn.commit()
    conn.close()


def create_database():
    if not os.path.exists('db.db'):
        conn = connect('db.db')
        c = conn.cursor()

        c.execute('''CREATE TABLE levels (
        id   INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        name TEXT);''')

        c.execute('''CREATE TABLE genres (
        id   INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        name TEXT);''')

        c.execute('''CREATE TABLE users (
        id         INTEGER PRIMARY KEY ASC AUTOINCREMENT,
        chat_id    INTEGER UNIQUE,
        status     TEXT,
        request    TEXT,
        ai_history TEXT,
        genre_id   INTEGER REFERENCES genres (id),
        level_id   INTEGER REFERENCES levels (id));''')
        conn.commit()
        conn.close()


if __name__ == "__main__":
    create_database()
    insert_levels(LEVELS)
    insert_genres(GENRES)
