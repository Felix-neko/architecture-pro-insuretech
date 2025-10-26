"""SQLAlchemy модели для сервиса управления клиентами.

Содержит:
- Customer: клиент с документами и родственниками
- Document: документы клиента (паспорт, водительские права и т.д.)
- Relative: родственники клиента (супруг, дети, родители и т.д.)
- Enums для типов документов и родственников
- Функцию populate_sample_data() для генерации тестовых данных
"""
from __future__ import annotations

import enum
import random
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import ForeignKey, Integer, String, Date, Enum as SQLEnum, func, select, Boolean, Float
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Синхронные импорты для функции populate_sample_data (инициализация БД)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


# Путь к файлу БД SQLite (создаётся в той же директории, что и models.py)
DB_FILENAME = "customer_service.db"
DB_PATH = Path(__file__).with_name(DB_FILENAME)

# Асинхронный движок для работы с SQLite через aiosqlite
# Используется в GraphQL-резолверах для неблокирующих запросов
async_engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}", future=True)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

# Синхронный движок для функции populate_sample_data (упрощает инициализацию)
sync_engine = create_engine(f"sqlite:///{DB_PATH}", future=True)


# Базовый класс для всех SQLAlchemy-моделей
class Base(DeclarativeBase):
    pass


class DocumentType(enum.Enum):
    """Типы документов, используемых при проверке благонадёжности клиента.
    
    - PASSPORT: паспорт гражданина
    - DRIVERS_LICENSE: водительское удостоверение
    - EMPLOYMENT_CERTIFICATE: справка с места работы
    - INCOME_CERTIFICATE: справка о доходах (2-НДФЛ и т.п.)
    - OTHER: прочие документы
    """
    PASSPORT = "PASSPORT"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    EMPLOYMENT_CERTIFICATE = "EMPLOYMENT_CERTIFICATE"
    INCOME_CERTIFICATE = "INCOME_CERTIFICATE"
    OTHER = "OTHER"


class RelationType(enum.Enum):
    """Типы родственников, учитываемых при страховании, кредитовании и проверке благонадёжности.
    
    - SPOUSE: супруг/супруга
    - CHILD: ребёнок
    - PARENT: родитель
    - SIBLING: брат/сестра
    - GUARDIAN: опекун/попечитель
    - BENEFICIARY: выгодоприобретатель (наследник по страховке)
    """
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    PARENT = "PARENT"
    SIBLING = "SIBLING"
    GUARDIAN = "GUARDIAN"
    BENEFICIARY = "BENEFICIARY"


class Customer(Base):
    """Модель клиента (аналог Client из OpenAPI-спецификации).
    
    Содержит базовую информацию о клиенте и связи с документами и родственниками.
    При удалении клиента автоматически удаляются все его документы и родственники (cascade).
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Уникальный идентификатор клиента
    name: Mapped[str] = mapped_column(String, nullable=False)  # ФИО клиента
    age: Mapped[int] = mapped_column(Integer, nullable=False)  # Возраст клиента
    email: Mapped[str] = mapped_column(String, nullable=False)  # Email клиента
    phone: Mapped[str] = mapped_column(String, nullable=False)  # Телефон клиента
    credit_score: Mapped[int] = mapped_column(Integer, nullable=False)  # Кредитный рейтинг (300-850)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Прошёл ли верификацию

    # Связь один-ко-многим: у клиента может быть несколько документов
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="customer", cascade="all, delete-orphan"
    )
    # Связь один-ко-многим: у клиента может быть несколько родственников
    relatives: Mapped[list["Relative"]] = relationship(
        "Relative", back_populates="customer", cascade="all, delete-orphan"
    )


class Document(Base):
    """Модель документа клиента (аналог Document из OpenAPI-спецификации).
    
    Хранит информацию о документах, удостоверяющих личность и финансовое состояние.
    Каждый документ принадлежит одному клиенту (связь через customer_id).
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Уникальный идентификатор документа
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)  # ID владельца документа
    type: Mapped[DocumentType] = mapped_column(SQLEnum(DocumentType), nullable=False)  # Тип документа (enum)
    number: Mapped[str] = mapped_column(String, nullable=False)  # Номер документа (серия + номер)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)  # Дата выдачи документа
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # Дата окончания действия (опционально)
    issuing_authority: Mapped[str] = mapped_column(String, nullable=False)  # Орган выдачи документа
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Прошёл ли проверку
    scan_url: Mapped[str | None] = mapped_column(String, nullable=True)  # URL скана документа

    # Обратная связь к клиенту
    customer: Mapped[Customer] = relationship("Customer", back_populates="documents")


class Relative(Base):
    """Модель родственника клиента (аналог Relative из OpenAPI-спецификации).
    
    Хранит информацию о родственниках, учитываемых при оценке рисков (страхование, кредит).
    Каждый родственник связан с одним клиентом (связь через customer_id).
    """
    __tablename__ = "relatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # Уникальный идентификатор родственника
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)  # ID клиента-владельца
    relation_type: Mapped[RelationType] = mapped_column(SQLEnum(RelationType), nullable=False)  # Тип родства (enum)
    name: Mapped[str] = mapped_column(String, nullable=False)  # ФИО родственника
    age: Mapped[int] = mapped_column(Integer, nullable=False)  # Возраст родственника
    phone: Mapped[str | None] = mapped_column(String, nullable=True)  # Телефон родственника
    is_dependent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # Является ли иждивенцем
    income_contribution: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Вклад в семейный доход (%)

    # Обратная связь к клиенту
    customer: Mapped[Customer] = relationship("Customer", back_populates="relatives")


def populate_sample_data() -> None:
    """Синхронная функция для первоначального заполнения БД тестовыми данными.
    
    Создаёт:
    - 5 клиентов с случайным возрастом (25-65 лет)
    - Для каждого клиента: от 0 до 4 документов (случайные типы, номера, даты)
    - Для каждого клиента: от 0 до 6 родственников (случайные типы родства, имена, возраст)
    
    Если БД уже содержит данные, функция завершается без изменений.
    """
    # Создаём таблицы, если их ещё нет
    Base.metadata.create_all(bind=sync_engine)
    
    with Session(sync_engine) as session:
        # Проверяем, есть ли уже данные в таблице customers
        has_data = session.scalar(select(func.count()).select_from(Customer))
        if has_data:
            print("База данных уже содержит данные, пропускаю загрузку примеров.")
            return

        # Список тестовых клиентов (ФИО)
        customer_names = [
            "Иванов Иван Иванович",
            "Петрова Мария Сергеевна",
            "Сидоров Алексей Петрович",
            "Кузнецова Елена Дмитриевна",
            "Смирнов Дмитрий Александрович",
        ]

        customers = []
        for i, name in enumerate(customer_names):
            age = random.randint(25, 65)  # Случайный возраст от 25 до 65 лет
            email = f"{name.split()[0].lower()}.{name.split()[2].lower()}@example.com"
            phone = f"+7-{random.randint(900, 999)}-{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}"
            credit_score = random.randint(300, 850)  # Кредитный рейтинг от 300 до 850
            is_verified = random.choice([True, False])
            customers.append(Customer(
                name=name,
                age=age,
                email=email,
                phone=phone,
                credit_score=credit_score,
                is_verified=is_verified
            ))

        # Добавляем клиентов в сессию и сохраняем (flush), чтобы получить их ID
        session.add_all(customers)
        session.flush()

        # Генерация документов для каждого клиента (от 0 до 4 документов на клиента)
        doc_types = list(DocumentType)
        for customer in customers:
            num_docs = random.randint(0, 4)  # Случайное количество документов (0-4)
            for _ in range(num_docs):
                doc_type = random.choice(doc_types)  # Случайный тип документа
                # Генерируем номер документа в формате "XXXX-YYYYYY"
                number = f"{random.randint(1000, 9999)}-{random.randint(100000, 999999)}"
                # Дата выдачи: от 1 до 10 лет назад
                issue_date = date.today() - timedelta(days=random.randint(365, 3650))
                expiry_date = None
                # Для паспортов и водительских прав устанавливаем срок действия (5-10 лет)
                if doc_type in [DocumentType.PASSPORT, DocumentType.DRIVERS_LICENSE]:
                    expiry_date = issue_date + timedelta(days=random.randint(1825, 3650))

                # Генерируем орган выдачи в зависимости от типа документа
                issuing_authorities = {
                    DocumentType.PASSPORT: ["МВД России", "УФМС", "ГУ МВД"],
                    DocumentType.DRIVERS_LICENSE: ["ГИБДД", "ГАИ"],
                    DocumentType.EMPLOYMENT_CERTIFICATE: ["ООО Рога и Копыта", "ПАО Газпром", "АО Сбербанк"],
                    DocumentType.INCOME_CERTIFICATE: ["ФНС России", "Налоговая инспекция"],
                    DocumentType.OTHER: ["Прочие органы"]
                }
                issuing_authority = random.choice(issuing_authorities.get(doc_type, ["Неизвестно"]))
                is_verified = random.choice([True, False])
                scan_url = f"https://storage.example.com/scans/{customer.id}/{random.randint(1000, 9999)}.pdf" if random.random() > 0.3 else None

                doc = Document(
                    customer_id=customer.id,
                    type=doc_type,
                    number=number,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                    issuing_authority=issuing_authority,
                    is_verified=is_verified,
                    scan_url=scan_url,
                )
                session.add(doc)

        # Генерация родственников для каждого клиента (от 0 до 6 родственников на клиента)
        relation_types = list(RelationType)
        # Список имён для генерации родственников
        relative_first_names = [
            "Анна", "Ольга", "Сергей", "Николай", "Екатерина",
            "Андрей", "Татьяна", "Владимир", "Наталья", "Михаил"
        ]
        for customer in customers:
            num_relatives = random.randint(0, 6)  # Случайное количество родственников (0-6)
            for _ in range(num_relatives):
                rel_type = random.choice(relation_types)  # Случайный тип родства
                # Генерируем ФИО: случайное имя + фамилия клиента
                rel_name = random.choice(relative_first_names) + " " + customer.name.split()[-1]
                rel_age = random.randint(1, 80)  # Случайный возраст от 1 до 80 лет

                # Генерируем телефон для родственника (70% вероятность)
                rel_phone = f"+7-{random.randint(900, 999)}-{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(10, 99)}" if random.random() > 0.3 else None
                # Иждивенцы: дети младше 18 или пожилые родители старше 65
                is_dependent = (rel_type == RelationType.CHILD and rel_age < 18) or (rel_type == RelationType.PARENT and rel_age > 65)
                # Вклад в семейный доход (0-100%)
                income_contribution = 0.0 if is_dependent else random.uniform(0.0, 100.0)

                relative = Relative(
                    customer_id=customer.id,
                    relation_type=rel_type,
                    name=rel_name,
                    age=rel_age,
                    phone=rel_phone,
                    is_dependent=is_dependent,
                    income_contribution=income_contribution,
                )
                session.add(relative)

        # Фиксируем все изменения в БД
        session.commit()
        print(f"Добавлены примеры: {len(customers)} клиентов с документами и родственниками.")


# Точка входа: при запуске файла напрямую (python models.py) создаём БД и заполняем тестовыми данными
if __name__ == "__main__":
    populate_sample_data()
