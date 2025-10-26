from __future__ import annotations

from pathlib import Path

from sqlalchemy import ForeignKey, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DB_FILENAME = "hello_graphql.db"
DB_PATH = Path(__file__).with_name(DB_FILENAME)

# Async engine для SQLite (требует aiosqlite)
async_engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", future=True)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine для populate_sample_data (для простоты инициализации)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sync_engine = create_engine(f"sqlite:///{DB_PATH}", future=True)


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    books: Mapped[list["Book"]] = relationship("Book", back_populates="author", cascade="all, delete-orphan")


class Publisher(Base):
    __tablename__ = "publishers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    editions: Mapped[list["Edition"]] = relationship(
        "Edition", back_populates="publisher", cascade="all, delete-orphan"
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), nullable=False)

    author: Mapped[Author] = relationship("Author", back_populates="books")
    editions: Mapped[list["Edition"]] = relationship("Edition", back_populates="book", cascade="all, delete-orphan")


class Edition(Base):
    __tablename__ = "editions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"), nullable=False)
    publisher_id: Mapped[int] = mapped_column(ForeignKey("publishers.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    book: Mapped[Book] = relationship("Book", back_populates="editions")
    publisher: Mapped[Publisher] = relationship("Publisher", back_populates="editions")


def populate_sample_data() -> None:
    """Синхронная функция для первоначального заполнения БД."""
    Base.metadata.create_all(bind=sync_engine)
    with Session(sync_engine) as session:
        has_data = session.scalar(select(func.count()).select_from(Author))
        if has_data:
            print("База данных уже содержит данные, пропускаю загрузку примеров.")
            return

        # Список авторов третьеразрядных российских детективов
        authors = [
            Author(name="Андрей Вяземский"),
            Author(name="Галина Бузина"),
            Author(name="Виктор Сыромятников"),
            Author(name="Лариса Погодина"),
            Author(name="Кирилл Бармаглот"),
        ]
        session.add_all(authors)
        session.flush()

        # Российские издательства 1990-х годов
        publishers = [
            Publisher(title="ЭКСМО"),
            Publisher(title="Вагриус"),
            Publisher(title="ОЛМА-Пресс"),
            Publisher(title="АСТ"),
            Publisher(title="Терра-Книжный клуб"),
        ]
        session.add_all(publishers)
        session.flush()

        # Бульварные детективы из 1990-х
        books = [
            Book(title="Пуля для районного авторитета", author=authors[0]),
            Book(title="Шериф из Митино", author=authors[0]),
            Book(title="Железнодорожный призрак", author=authors[1]),
            Book(title="Привокзальная мафия", author=authors[1]),
            Book(title="Ларьки под колпаком", author=authors[2]),
            Book(title="Чемодан с рублями", author=authors[2]),
            Book(title="Сыщицы с Арбата", author=authors[3]),
            Book(title="Убийство в доме быта", author=authors[3]),
            Book(title="Секретный ход под рынком", author=authors[4]),
            Book(title="Похищение медной тетради", author=authors[4]),
        ]
        session.add_all(books)
        session.flush()

        # Реальные издания 1990-х для каждого романа
        edition_specs = [
            (books[0], publishers[0], 1995),
            (books[0], publishers[1], 1997),
            (books[1], publishers[2], 1996),
            (books[1], publishers[0], 1999),
            (books[2], publishers[1], 1994),
            (books[2], publishers[3], 1998),
            (books[3], publishers[3], 1995),
            (books[3], publishers[4], 1997),
            (books[4], publishers[2], 1993),
            (books[4], publishers[0], 1996),
            (books[5], publishers[4], 1994),
            (books[5], publishers[1], 1998),
            (books[6], publishers[3], 1995),
            (books[6], publishers[2], 1999),
            (books[7], publishers[4], 1996),
            (books[7], publishers[0], 1998),
            (books[8], publishers[1], 1993),
            (books[8], publishers[2], 1997),
            (books[9], publishers[3], 1994),
            (books[9], publishers[4], 1996),
        ]

        editions = [Edition(book=book, publisher=publisher, year=year) for book, publisher, year in edition_specs]

        session.add_all(editions)
        session.commit()
        print("Добавлены примеры: 5 авторов, 10 книг, 20 изданий, 5 издательств.")


if __name__ == "__main__":
    populate_sample_data()
