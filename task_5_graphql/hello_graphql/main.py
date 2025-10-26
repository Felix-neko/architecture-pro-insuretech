from typing import List, Optional

import asyncio
import logging

from fastapi import FastAPI
import uvicorn
import strawberry
from strawberry.dataloader import DataLoader
from strawberry.fastapi import GraphQLRouter
from sqlalchemy import select

from sqla_models import (
    Author as AuthorModel,
    Book as BookModel,
    Edition as EditionModel,
    Publisher as PublisherModel,
    AsyncSessionLocal,
)

logger = logging.getLogger(__name__)


@strawberry.type
class Author:
    id: int
    name: str

    @strawberry.field
    async def books(self) -> List["Book"]:
        """Ленивая загрузка книг автора."""
        return await books_by_author_loader.load(self.id)


@strawberry.type
class Publisher:
    id: int
    title: str

    @strawberry.field
    async def books(self) -> List["Book"]:
        """Ленивая загрузка книг издательства."""
        return await books_by_publisher_loader.load(self.id)

    @strawberry.field
    async def editions(self) -> List["Edition"]:
        """Ленивая загрузка изданий издательства."""
        return await editions_by_publisher_loader.load(self.id)


@strawberry.type
class Edition:
    id: int
    publisher_id: Optional[int]
    year: int

    @strawberry.field
    async def publisher(self) -> Optional[Publisher]:
        """Ленивая загрузка издательства через DataLoader."""
        if self.publisher_id is None:
            return None
        return await publisher_loader.load(self.publisher_id)


@strawberry.type
class Book:
    id: int
    title: str
    author_id: int

    @strawberry.field
    async def author(self) -> Author:
        """Ленивая загрузка автора через DataLoader."""
        return await author_loader.load(self.author_id)

    @strawberry.field
    async def editions(self) -> List[Edition]:
        """Ленивая загрузка изданий через DataLoader."""
        return await editions_by_book_loader.load(self.id)


@strawberry.type
class User:
    id: int
    name: str


# ============ DataLoader функции ============


async def load_authors(keys: List[int]) -> List[Author]:
    """Батчинг загрузки авторов по списку ID."""
    logger.info("DataLoader load_authors keys=%s", keys)
    async with AsyncSessionLocal() as session:
        stmt = select(AuthorModel).where(AuthorModel.id.in_(keys))
        result = await session.execute(stmt)
        authors = result.scalars().all()
        author_map = {a.id: Author(id=a.id, name=a.name) for a in authors}
        # Возвращаем в том же порядке, что и keys (важно для DataLoader!)
        return [author_map.get(k) for k in keys]


async def load_publishers(keys: List[int]) -> List[Publisher]:
    """Батчинг загрузки издательств по списку ID."""
    logger.info("DataLoader load_publishers keys=%s", keys)
    async with AsyncSessionLocal() as session:
        stmt = select(PublisherModel).where(PublisherModel.id.in_(keys))
        result = await session.execute(stmt)
        publishers = result.scalars().all()
        publisher_map = {p.id: Publisher(id=p.id, title=p.title) for p in publishers}
        return [publisher_map.get(k) for k in keys]


async def load_books_by_author(keys: List[int]) -> List[List[Book]]:
    """Батчинг загрузки книг по авторам."""
    logger.info("DataLoader load_books_by_author keys=%s", keys)
    async with AsyncSessionLocal() as session:
        stmt = select(BookModel).where(BookModel.author_id.in_(keys))
        result = await session.execute(stmt)
        books = result.scalars().all()

        books_map: dict[int, list[Book]] = {}
        for book in books:
            books_map.setdefault(book.author_id, []).append(
                Book(id=book.id, title=book.title, author_id=book.author_id)
            )

        return [books_map.get(k, []) for k in keys]


async def load_books_by_publisher(keys: List[int]) -> List[List[Book]]:
    """Батчинг загрузки книг по издательствам на основе изданий."""
    logger.info("DataLoader load_books_by_publisher keys=%s", keys)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(EditionModel.publisher_id, BookModel)
            .join(BookModel, EditionModel.book_id == BookModel.id)
            .where(EditionModel.publisher_id.in_(keys))
        )
        result = await session.execute(stmt)
        rows = result.all()

        books_map: dict[int, list[Book]] = {}
        seen_map: dict[int, set[int]] = {}
        for publisher_id, book in rows:
            seen = seen_map.setdefault(publisher_id, set())
            if book.id in seen:
                continue
            seen.add(book.id)
            books_map.setdefault(publisher_id, []).append(Book(id=book.id, title=book.title, author_id=book.author_id))

        return [books_map.get(k, []) for k in keys]


async def load_editions_by_book(keys: List[int]) -> List[List[Edition]]:
    """Батчинг загрузки изданий по списку book_id."""
    logger.info("DataLoader load_editions_by_book keys=%s", keys)
    async with AsyncSessionLocal() as session:
        stmt = select(EditionModel).where(EditionModel.book_id.in_(keys))
        result = await session.execute(stmt)
        editions = result.scalars().all()
        # Группируем издания по book_id
        editions_map = {}
        for ed in editions:
            editions_map.setdefault(ed.book_id, []).append(
                Edition(id=ed.id, publisher_id=ed.publisher_id, year=ed.year)
            )
        # Возвращаем списки в порядке keys
        return [editions_map.get(k, []) for k in keys]


async def load_editions_by_publisher(keys: List[int]) -> List[List[Edition]]:
    """Батчинг загрузки изданий по издательствам."""
    logger.info("DataLoader load_editions_by_publisher keys=%s", keys)
    async with AsyncSessionLocal() as session:
        stmt = select(EditionModel).where(EditionModel.publisher_id.in_(keys))
        result = await session.execute(stmt)
        editions = result.scalars().all()

        editions_map: dict[int, list[Edition]] = {}
        for ed in editions:
            editions_map.setdefault(ed.publisher_id, []).append(
                Edition(id=ed.id, publisher_id=ed.publisher_id, year=ed.year)
            )

        return [editions_map.get(k, []) for k in keys]


# Создаём глобальные DataLoader'ы
author_loader = DataLoader(load_fn=load_authors)
publisher_loader = DataLoader(load_fn=load_publishers)
books_by_author_loader = DataLoader(load_fn=load_books_by_author)
books_by_publisher_loader = DataLoader(load_fn=load_books_by_publisher)
editions_by_book_loader = DataLoader(load_fn=load_editions_by_book)
editions_by_publisher_loader = DataLoader(load_fn=load_editions_by_publisher)


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "hello-1"

    @strawberry.field
    def world(self) -> str:
        return "world-1"

    @strawberry.field
    async def book(self, id: int) -> Optional[Book]:
        """Получить книгу по ID из SQLite (async + DataLoader)."""
        async with AsyncSessionLocal() as session:
            stmt = select(BookModel).where(BookModel.id == id)
            result = await session.execute(stmt)
            book_model = result.scalar_one_or_none()
            if not book_model:
                return None
            return Book(id=book_model.id, title=book_model.title, author_id=book_model.author_id)

    @strawberry.field
    async def author(self, id: int) -> Optional[Author]:
        """Получить автора по ID из SQLite (async)."""
        async with AsyncSessionLocal() as session:
            author_model = await session.get(AuthorModel, id)
            if not author_model:
                return None
            return Author(id=author_model.id, name=author_model.name)

    @strawberry.field
    async def publisher(self, id: int) -> Optional[Publisher]:
        """Получить издательство по ID из SQLite (async)."""
        async with AsyncSessionLocal() as session:
            publisher_model = await session.get(PublisherModel, id)
            if not publisher_model:
                return None
            return Publisher(id=publisher_model.id, title=publisher_model.title)

    @strawberry.field
    async def edition(self, id: int) -> Optional[Edition]:
        """Получить издание по ID из SQLite (async + DataLoader)."""
        async with AsyncSessionLocal() as session:
            stmt = select(EditionModel).where(EditionModel.id == id)
            result = await session.execute(stmt)
            edition_model = result.scalar_one_or_none()
            if not edition_model:
                return None
            return Edition(id=edition_model.id, publisher_id=edition_model.publisher_id, year=edition_model.year)

    @strawberry.field
    async def books(self, ids: Optional[List[int]] = None) -> List[Book]:
        """Получить все книги или книги по списку ID из SQLite (async + DataLoader)."""
        async with AsyncSessionLocal() as session:
            stmt = select(BookModel)
            if ids is not None:
                stmt = stmt.where(BookModel.id.in_(ids))

            result = await session.execute(stmt)
            book_models = result.scalars().all()
            return [Book(id=bm.id, title=bm.title, author_id=bm.author_id) for bm in book_models]


@strawberry.type
class Query2:
    @strawberry.field
    def foo(self) -> str:
        return "foo-1"

    @strawberry.field
    def bar(self) -> str:
        return "bar-1"


schema = strawberry.Schema(Query, types=[Book, Author, Publisher, Edition])

graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = uvicorn.Config(app, host="0.0.0.0", port=9000)
    server = uvicorn.Server(config)
    asyncio.run(server.serve())
