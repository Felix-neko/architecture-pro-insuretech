"""FastAPI + Strawberry GraphQL приложение для управления клиентами.

Предоставляет GraphQL API для работы с клиентами, их документами и родственниками.
Использует async SQLAlchemy + SQLite для хранения данных и DataLoader для оптимизации запросов.

Запуск: python main.py (сервер стартует на http://localhost:9001/graphql)
"""
from typing import AsyncGenerator, List, Optional
from datetime import date
import enum

import asyncio
import logging

from fastapi import FastAPI
import uvicorn
import strawberry
from strawberry.dataloader import DataLoader
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info
from strawberry.schema.config import StrawberryConfig
from strawberry.schema.name_converter import NameConverter
from sqlalchemy import select
from sqlalchemy.orm import load_only

from models import (
    Customer as CustomerModel,
    Document as DocumentModel,
    Relative as RelativeModel,
    DocumentType as DocumentTypeEnum,
    RelationType as RelationTypeEnum,
    AsyncSessionLocal,
)

# Логгер для отслеживания вызовов DataLoader'ов
logger = logging.getLogger(__name__)


# ============ Strawberry Enums ============
# Создаём отдельные Strawberry Enum'ы для GraphQL API (должны наследоваться от enum.Enum)


@strawberry.enum
class DocumentType(enum.Enum):
    """Типы документов для GraphQL API.
    
    Соответствует models.DocumentType (SQLAlchemy Enum).
    """
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    EMPLOYMENT_CERTIFICATE = "EMPLOYMENT_CERTIFICATE"
    INCOME_CERTIFICATE = "INCOME_CERTIFICATE"
    OTHER = "OTHER"


@strawberry.enum
class RelationType(enum.Enum):
    """Типы родственников для GraphQL API.
    
    Соответствует models.RelationType (SQLAlchemy Enum).
    """
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    PARENT = "PARENT"
    SIBLING = "SIBLING"
    GUARDIAN = "GUARDIAN"
    BENEFICIARY = "BENEFICIARY"


# ============ Strawberry Types ============
# GraphQL-типы, соответствующие SQLAlchemy-моделям из models.py


@strawberry.type(description="Документ клиента (паспорт, водительские права и т.д.)")
class Document:
    """GraphQL-тип для документа клиента.
    
    Соответствует models.Document из БД.
    Поля опциональны для поддержки селективной загрузки.
    """
    id: int = strawberry.field(description="Уникальный идентификатор документа")
    customer_id: Optional[int] = strawberry.field(default=None, description="ID клиента-владельца документа")
    type: Optional[DocumentType] = strawberry.field(default=None, description="Тип документа")
    number: Optional[str] = strawberry.field(default=None, description="Номер документа (серия + номер)")
    issue_date: Optional[date] = strawberry.field(default=None, description="Дата выдачи документа")
    expiry_date: Optional[date] = strawberry.field(default=None, description="Дата окончания действия документа")
    issuing_authority: Optional[str] = strawberry.field(default=None, description="Орган выдачи документа (МВД, ГИБДД и т.д.)")
    is_verified: Optional[bool] = strawberry.field(default=None, description="Прошёл ли документ проверку подлинности")
    scan_url: Optional[str] = strawberry.field(default=None, description="URL скана документа в хранилище")


@strawberry.type(description="Родственник клиента (супруг, ребёнок, родитель и т.д.)")
class Relative:
    """GraphQL-тип для родственника клиента.
    
    Соответствует models.Relative из БД.
    Поля опциональны для поддержки селективной загрузки.
    """
    id: int = strawberry.field(description="Уникальный идентификатор родственника")
    customer_id: Optional[int] = strawberry.field(default=None, description="ID клиента, к которому относится родственник")
    relation_type: Optional[RelationType] = strawberry.field(default=None, description="Тип родства")
    name: Optional[str] = strawberry.field(default=None, description="ФИО родственника")
    age: Optional[int] = strawberry.field(default=None, description="Возраст родственника")
    phone: Optional[str] = strawberry.field(default=None, description="Контактный телефон родственника")
    is_dependent: Optional[bool] = strawberry.field(default=None, description="Является ли иждивенцем (дети <18, родители >65)")
    income_contribution: Optional[float] = strawberry.field(default=None, description="Вклад в семейный доход (%)")


@strawberry.type(description="Клиент страхового агрегатора")
class Customer:
    """GraphQL-тип для клиента.
    
    Соответствует models.Customer из БД.
    Поля documents и relatives загружаются лениво через DataLoader для оптимизации.
    Поля опциональны для поддержки селективной загрузки (загружаются только запрошенные поля).
    """
    id: int = strawberry.field(description="Уникальный идентификатор клиента")
    name: Optional[str] = strawberry.field(default=None, description="ФИО клиента")
    age: Optional[int] = strawberry.field(default=None, description="Возраст клиента")
    email: Optional[str] = strawberry.field(default=None, description="Email клиента")
    phone: Optional[str] = strawberry.field(default=None, description="Контактный телефон клиента")
    credit_score: Optional[int] = strawberry.field(default=None, description="Кредитный рейтинг (300-850)")
    is_verified: Optional[bool] = strawberry.field(default=None, description="Прошёл ли клиент верификацию личности")

    @strawberry.field(description="Список документов клиента (паспорт, водительские права и т.д.)")
    async def documents(self) -> List[Document]:
        """Ленивая загрузка документов клиента через DataLoader.

        Вызывается только если клиент запросил поле documents в GraphQL-запросе.
        DataLoader автоматически группирует запросы для нескольких клиентов в один батч.
        """
        logger.info("Customer.documents -> load documents for customer_id=%s", self.id)
        return await documents_by_customer_loader.load(self.id)

    @strawberry.field(description="Список родственников клиента (супруг, дети, родители и т.д.)")
    async def relatives(self) -> List[Relative]:
        """Ленивая загрузка родственников клиента через DataLoader.

        Вызывается только если клиент запросил поле relatives в GraphQL-запросе.
        DataLoader автоматически группирует запросы для нескольких клиентов в один батч.
        """
        logger.info("Customer.relatives -> load relatives for customer_id=%s", self.id)
        return await relatives_by_customer_loader.load(self.id)


# ============ DataLoader функции ============
# Функции для батчинга запросов к БД, решают проблему N+1 запросов


def get_requested_fields(info: Info, type_name: str) -> List[str]:
    """Извлекает список запрошенных полей из GraphQL query для заданного типа.
    
    Args:
        info: Strawberry Info объект с информацией о GraphQL запросе
        type_name: Имя типа (например, 'documents', 'relatives', 'customer')
    
    Returns:
        Список имён полей, запрошенных в GraphQL query
    """
    # Получаем выбранные поля из GraphQL query
    selections = []
    for field in info.selected_fields:
        if field.name == type_name:
            # Для вложенных полей (documents, relatives)
            for subfield in field.selections:
                selections.append(subfield.name)
        else:
            # Для полей верхнего уровня
            selections.append(field.name)
    
    return selections if selections else None


async def load_documents_by_customer(keys: List[int]) -> List[List[Document]]:
    """Батчинг загрузки документов по списку customer_id.
    
    Вместо N запросов (по одному на каждого клиента) выполняет один запрос
    с WHERE customer_id IN (...) и группирует результаты по customer_id.
    
    Args:
        keys: Список ID клиентов, для которых нужно загрузить документы
    
    Returns:
        Список списков документов в том же порядке, что и keys.
        Для клиентов без документов возвращается пустой список.
    """
    logger.info("DataLoader load_documents_by_customer keys=%s", keys)
    async with AsyncSessionLocal() as session:
        # Один запрос для всех клиентов из keys
        # Загружаем все поля, т.к. DataLoader не имеет доступа к Info
        stmt = select(DocumentModel).where(DocumentModel.customer_id.in_(keys))
        result = await session.execute(stmt)
        documents = result.scalars().all()

        # Группируем документы по customer_id
        docs_map: dict[int, list[Document]] = {}
        for doc in documents:
            docs_map.setdefault(doc.customer_id, []).append(
                Document(
                    id=doc.id,
                    customer_id=doc.customer_id,
                    type=DocumentType(doc.type.value),  # Конвертируем SQLAlchemy enum через .value
                    number=doc.number,
                    issue_date=doc.issue_date,
                    expiry_date=doc.expiry_date,
                    issuing_authority=doc.issuing_authority,
                    is_verified=doc.is_verified,
                    scan_url=doc.scan_url,
                )
            )

        # Возвращаем списки в том же порядке, что и keys (важно для DataLoader!)
        return [docs_map.get(k, []) for k in keys]


async def load_relatives_by_customer(keys: List[int]) -> List[List[Relative]]:
    """Батчинг загрузки родственников по списку customer_id.
    
    Вместо N запросов (по одному на каждого клиента) выполняет один запрос
    с WHERE customer_id IN (...) и группирует результаты по customer_id.
    
    Args:
        keys: Список ID клиентов, для которых нужно загрузить родственников
    
    Returns:
        Список списков родственников в том же порядке, что и keys.
        Для клиентов без родственников возвращается пустой список.
    """
    logger.info("DataLoader load_relatives_by_customer keys=%s", keys)
    async with AsyncSessionLocal() as session:
        # Один запрос для всех клиентов из keys
        # Загружаем все поля, т.к. DataLoader не имеет доступа к Info
        stmt = select(RelativeModel).where(RelativeModel.customer_id.in_(keys))
        result = await session.execute(stmt)
        relatives = result.scalars().all()

        # Группируем родственников по customer_id
        rels_map: dict[int, list[Relative]] = {}
        for rel in relatives:
            rels_map.setdefault(rel.customer_id, []).append(
                Relative(
                    id=rel.id,
                    customer_id=rel.customer_id,
                    relation_type=RelationType(rel.relation_type.value),  # Конвертируем SQLAlchemy enum через .value
                    name=rel.name,
                    age=rel.age,
                    phone=rel.phone,
                    is_dependent=rel.is_dependent,
                    income_contribution=rel.income_contribution,
                )
            )

        # Возвращаем списки в том же порядке, что и keys (важно для DataLoader!)
        return [rels_map.get(k, []) for k in keys]


# Создаём глобальные DataLoader'ы для оптимизации запросов
# DataLoader автоматически группирует запросы в батчи и кеширует результаты в рамках одного GraphQL-запроса
documents_by_customer_loader = DataLoader(load_fn=load_documents_by_customer)
relatives_by_customer_loader = DataLoader(load_fn=load_relatives_by_customer)


# ============ GraphQL Query ============
# Корневые запросы GraphQL API


@strawberry.type
class Query:
    """Корневой тип Query для GraphQL API.
    
    Содержит все доступные запросы для чтения данных.
    """
    
    @strawberry.field
    async def customer(self, id: int, info: Info) -> Optional[Customer]:
        """Получить клиента по ID с селективной загрузкой полей.
        
        Args:
            id: Уникальный идентификатор клиента
            info: Strawberry Info объект для определения запрошенных полей
        
        Returns:
            Customer или None, если клиент не найден
        
        Пример запроса:
            query {
              customer(id: 1) {
                id
                name
                age
                documents { id type number }
                relatives { id relationType name }
              }
            }
        """
        async with AsyncSessionLocal() as session:
            # Определяем, какие поля запрошены в GraphQL query
            # Нужно извлечь поля из selections первого уровня
            requested_fields = []
            for field in info.selected_fields:
                # Если это поле 'customer', берём его подполя (selections)
                if hasattr(field, 'selections') and field.selections:
                    requested_fields.extend([subfield.name for subfield in field.selections])
                else:
                    requested_fields.append(field.name)
            
            logger.info(f"customer(id={id}) requested fields: {requested_fields}")
            
            # Фильтруем только поля модели Customer (исключаем documents, relatives)
            # Это поля, которые нужно загрузить из БД
            model_fields = [f for f in requested_fields if f in [
                'id', 'name', 'age', 'email', 'phone', 'credit_score', 'is_verified'
            ]]
            
            # Если не запрошено ни одно поле модели (только documents/relatives),
            # всё равно загружаем id
            if not model_fields:
                model_fields = ['id']
            elif 'id' not in model_fields:
                model_fields.append('id')
            
            logger.info(f"customer(id={id}) loading fields from DB: {model_fields}")
            
            # Создаём запрос с селективной загрузкой полей
            stmt = select(CustomerModel).where(CustomerModel.id == id).options(
                load_only(*[getattr(CustomerModel, f) for f in model_fields])
            )
            result = await session.execute(stmt)
            customer_model = result.scalar_one_or_none()
            
            if not customer_model:
                return None
            
            # Создаём объект Customer только с запрошенными полями
            # ID всегда должен быть включён (обязательное поле)
            customer_data = {'id': customer_model.id}
            for field in model_fields:
                if field != 'id':  # id уже добавлен
                    customer_data[field] = getattr(customer_model, field)
            
            return Customer(**customer_data)

    @strawberry.field
    async def customers(self, ids: Optional[List[int]] = None, info: Info = None) -> List[Customer]:
        """Получить всех клиентов или клиентов по списку ID с селективной загрузкой полей.
        
        Args:
            ids: Опциональный список ID клиентов для фильтрации.
                 Если не указан, возвращаются все клиенты.
            info: Strawberry Info объект для определения запрошенных полей
        
        Returns:
            Список клиентов (может быть пустым)
        
        Пример запроса:
            query {
              customers {
                id
                name
                documents { type }
              }
            }
        """
        async with AsyncSessionLocal() as session:
            # Определяем, какие поля запрошены в GraphQL query
            # Нужно извлечь поля из selections первого уровня
            requested_fields = []
            if info:
                for field in info.selected_fields:
                    # Если это поле 'customers', берём его подполя (selections)
                    if hasattr(field, 'selections') and field.selections:
                        requested_fields.extend([subfield.name for subfield in field.selections])
                    else:
                        requested_fields.append(field.name)
            
            logger.info(f"customers(ids={ids}) requested fields: {requested_fields}")
            
            # Фильтруем только поля модели Customer (исключаем documents, relatives)
            model_fields = [f for f in requested_fields if f in [
                'id', 'name', 'age', 'email', 'phone', 'credit_score', 'is_verified'
            ]]
            
            # Если поля не указаны, загружаем все
            if not model_fields:
                model_fields = ['id', 'name', 'age', 'email', 'phone', 'credit_score', 'is_verified']
            
            # Всегда включаем id для корректной работы
            if 'id' not in model_fields:
                model_fields.append('id')
            
            stmt = select(CustomerModel)
            if ids is not None:
                stmt = stmt.where(CustomerModel.id.in_(ids))
            
            # Применяем селективную загрузку полей
            stmt = stmt.options(
                load_only(*[getattr(CustomerModel, f) for f in model_fields])
            )

            result = await session.execute(stmt)
            customer_models = result.scalars().all()
            
            # Создаём объекты Customer только с запрошенными полями
            # ID всегда должен быть включён (обязательное поле)
            customers = []
            for c in customer_models:
                customer_data = {'id': c.id}
                for field in model_fields:
                    if field != 'id':  # id уже добавлен
                        customer_data[field] = getattr(c, field)
                customers.append(Customer(**customer_data))
            
            return customers

    @strawberry.field
    async def document(self, id: int, info: Info) -> Optional[Document]:
        """Получить документ по ID с селективной загрузкой полей.
        
        Args:
            id: Уникальный идентификатор документа
            info: Strawberry Info объект для определения запрошенных полей
        
        Returns:
            Document или None, если документ не найден
        
        Пример запроса:
            query {
              document(id: 1) {
                id
                type
                number
                issuing_authority
              }
            }
        """
        async with AsyncSessionLocal() as session:
            # Определяем, какие поля запрошены в GraphQL query
            requested_fields = []
            for field in info.selected_fields:
                if hasattr(field, 'selections') and field.selections:
                    requested_fields.extend([subfield.name for subfield in field.selections])
                else:
                    requested_fields.append(field.name)
            
            logger.info(f"document(id={id}) requested fields: {requested_fields}")
            
            # Фильтруем только поля модели Document
            model_fields = [f for f in requested_fields if f in [
                'id', 'customer_id', 'type', 'number', 'issue_date', 'expiry_date',
                'issuing_authority', 'is_verified', 'scan_url'
            ]]
            
            # Всегда включаем id
            if not model_fields:
                model_fields = ['id']
            elif 'id' not in model_fields:
                model_fields.append('id')
            
            logger.info(f"document(id={id}) loading fields from DB: {model_fields}")
            
            # Создаём запрос с селективной загрузкой полей
            stmt = select(DocumentModel).where(DocumentModel.id == id).options(
                load_only(*[getattr(DocumentModel, f) for f in model_fields])
            )
            result = await session.execute(stmt)
            document_model = result.scalar_one_or_none()
            
            if not document_model:
                return None
            
            # Создаём объект Document только с запрошенными полями
            document_data = {'id': document_model.id}
            for field in model_fields:
                if field != 'id':
                    value = getattr(document_model, field)
                    # Конвертируем SQLAlchemy enum в Strawberry enum
                    if field == 'type' and value is not None:
                        value = DocumentType(value.value)
                    document_data[field] = value
            
            return Document(**document_data)

    @strawberry.field
    async def relative(self, id: int, info: Info) -> Optional[Relative]:
        """Получить родственника по ID с селективной загрузкой полей.
        
        Args:
            id: Уникальный идентификатор родственника
            info: Strawberry Info объект для определения запрошенных полей
        
        Returns:
            Relative или None, если родственник не найден
        
        Пример запроса:
            query {
              relative(id: 1) {
                id
                name
                relation_type
                is_dependent
              }
            }
        """
        async with AsyncSessionLocal() as session:
            # Определяем, какие поля запрошены в GraphQL query
            requested_fields = []
            for field in info.selected_fields:
                if hasattr(field, 'selections') and field.selections:
                    requested_fields.extend([subfield.name for subfield in field.selections])
                else:
                    requested_fields.append(field.name)
            
            logger.info(f"relative(id={id}) requested fields: {requested_fields}")
            
            # Фильтруем только поля модели Relative
            model_fields = [f for f in requested_fields if f in [
                'id', 'customer_id', 'relation_type', 'name', 'age',
                'phone', 'is_dependent', 'income_contribution'
            ]]
            
            # Всегда включаем id
            if not model_fields:
                model_fields = ['id']
            elif 'id' not in model_fields:
                model_fields.append('id')
            
            logger.info(f"relative(id={id}) loading fields from DB: {model_fields}")
            
            # Создаём запрос с селективной загрузкой полей
            stmt = select(RelativeModel).where(RelativeModel.id == id).options(
                load_only(*[getattr(RelativeModel, f) for f in model_fields])
            )
            result = await session.execute(stmt)
            relative_model = result.scalar_one_or_none()
            
            if not relative_model:
                return None
            
            # Создаём объект Relative только с запрошенными полями
            relative_data = {'id': relative_model.id}
            for field in model_fields:
                if field != 'id':
                    value = getattr(relative_model, field)
                    # Конвертируем SQLAlchemy enum в Strawberry enum
                    if field == 'relation_type' and value is not None:
                        value = RelationType(value.value)
                    relative_data[field] = value
            
            return Relative(**relative_data)


# ============ GraphQL Mutation ============
# Мутации для изменения данных


@strawberry.input
class CreateCustomerInput:
    """Входные данные для создания нового клиента."""
    name: str  # ФИО клиента
    age: int  # Возраст клиента
    email: str  # Email клиента
    phone: str  # Телефон клиента
    credit_score: int  # Кредитный рейтинг (300-850)
    is_verified: bool = False  # Прошёл ли верификацию


@strawberry.type
class Mutation:
    """Корневой тип Mutation для GraphQL API.
    
    Содержит все доступные мутации для изменения данных.
    """
    
    @strawberry.mutation
    async def create_customer(self, input: CreateCustomerInput) -> Customer:
        """Создать нового клиента в БД.
        
        Args:
            input: Данные нового клиента (name, age, email, phone, credit_score, is_verified)
        
        Returns:
            Созданный клиент с присвоенным ID
        
        Пример мутации:
            mutation {
              createCustomer(input: {
                name: "Иванов Иван Иванович",
                age: 35,
                email: "ivanov@example.com",
                phone: "+7-900-123-45-67",
                creditScore: 750,
                isVerified: true
              }) {
                id
                name
                age
                email
              }
            }
        """
        async with AsyncSessionLocal() as session:
            # Создаём новую запись в БД
            customer_model = CustomerModel(
                name=input.name,
                age=input.age,
                email=input.email,
                phone=input.phone,
                credit_score=input.credit_score,
                is_verified=input.is_verified
            )
            session.add(customer_model)
            await session.commit()
            # Обновляем объект, чтобы получить присвоенный ID
            await session.refresh(customer_model)

        return Customer(
            id=customer_model.id,
            name=customer_model.name,
            age=customer_model.age,
            email=customer_model.email,
            phone=customer_model.phone,
            credit_score=customer_model.credit_score,
            is_verified=customer_model.is_verified
        )


# ============ GraphQL Subscription ============
# Подписки для потоковой передачи данных (WebSocket)


@strawberry.type
class Subscription:
    """Корневой тип Subscription для GraphQL API.
    
    Содержит все доступные подписки для получения потоковых данных.
    """
    
    @strawberry.subscription
    async def ticker(self, delay: float = 1.0, n_ticks: int = 10) -> AsyncGenerator[str, None]:
        """Синтетическая подписка для демонстрации возможностей GraphQL Subscriptions.
        
        Генерирует события с заданным интервалом и ограниченным количеством.
        
        Args:
            delay: Задержка между событиями в секундах (по умолчанию 1.0)
            n_ticks: Количество событий (по умолчанию 10)
        
        Yields:
            Строки вида "tick #N (delay=Xs)"
        
        Пример подписки:
            subscription {
              ticker(delay: 0.5, nTicks: 5)
            }
        """
        counter = 0
        while counter < n_ticks:
            await asyncio.sleep(delay)
            counter += 1
            yield f"tick #{counter} (delay={delay}s)"


# ============ Schema & App ============
# Создание GraphQL-схемы и FastAPI-приложения


# Создаём GraphQL-схему с использованием snake_case для имён полей
# По умолчанию Strawberry использует camelCase, но мы переключаем на snake_case
schema = strawberry.Schema(
    Query,
    mutation=Mutation,
    subscription=Subscription,
    config=StrawberryConfig(
        name_converter=NameConverter(auto_camel_case=False)
    )
)

# Создаём GraphQL-роутер для интеграции с FastAPI
graphql_app = GraphQLRouter(schema)

# Создаём FastAPI-приложение
app = FastAPI()
# Подключаем GraphQL-роутер по пути /graphql
# GraphiQL UI будет доступен по адресу http://localhost:9001/graphql
app.include_router(graphql_app, prefix="/graphql")


# Эндпоинт для скачивания GraphQL-схемы в формате SDL
@app.get("/schema.graphql")
async def get_schema_sdl():
    """Возвращает GraphQL-схему в формате SDL (Schema Definition Language)."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(str(schema), media_type="text/plain")


# Эндпоинт для скачивания GraphQL-схемы в формате JSON (introspection)
@app.get("/schema.json")
async def get_schema_json():
    """Возвращает GraphQL-схему в формате JSON (introspection query result)."""
    from graphql import get_introspection_query, graphql_sync
    
    introspection_query = get_introspection_query()
    result = graphql_sync(schema._schema, introspection_query)
    return result.data


# Точка входа: при запуске файла напрямую (python main.py) стартуем сервер
if __name__ == "__main__":
    # Настраиваем логирование для отслеживания вызовов DataLoader'ов
    logging.basicConfig(level=logging.INFO)
    # Конфигурируем uvicorn для запуска на порту 9001
    config = uvicorn.Config(app, host="0.0.0.0", port=9001)
    server = uvicorn.Server(config)
    # Запускаем сервер асинхронно
    asyncio.run(server.serve())
