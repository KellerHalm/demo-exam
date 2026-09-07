import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = Path(__file__).resolve().parent / "blog.db"
DATABASE_URL = "sqlite:///" + str(DB_PATH)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    secret_note: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    content: Mapped[str]
    author: Mapped[str]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        user_count = session.scalar(
            select(func.count()).select_from(User)
        )

        if user_count == 0:
            session.add(
                User(
                    email="user@example.com",
                    password_hash=hash_password("password"),
                    secret_note="Secret note: only authenticated users can see this."
                )
            )
            session.commit()


def get_user_by_email(email: str):
    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.email == email)
        )

        if user is None:
            return None

        return {
            "id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "secret_note": user.secret_note,
            "created_at": user.created_at
        }


def get_user_by_id(user_id: int):
    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.id == user_id)
        )

        if user is None:
            return None

        return {
            "id": user.id,
            "email": user.email,
            "password_hash": user.password_hash,
            "secret_note": user.secret_note,
            "created_at": user.created_at
        }


def get_posts():
    with SessionLocal() as session:
        posts = session.scalars(
            select(Post).order_by(Post.id.desc())
        ).all()

        return [
            {
                "id": post.id,
                "title": post.title,
                "content": post.content,
                "author": post.author
            }
            for post in posts
        ]


def create_post(title: str, content: str, author: str):
    with SessionLocal() as session:
        post = Post(title=title, content=content, author=author)
        session.add(post)
        session.commit()
        session.refresh(post)

        return {
            "id": post.id,
            "title": post.title,
            "content": post.content,
            "author": post.author
        }