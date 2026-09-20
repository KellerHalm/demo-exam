import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select, func, inspect, text
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
    username: Mapped[str] = mapped_column(unique=True)
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

    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "username" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR"))
            connection.execute(text("UPDATE users SET username = substr(email, 1, instr(email, '@') - 1)"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))

    with SessionLocal() as session:
        user_count = session.scalar(
            select(func.count()).select_from(User)
        )

        if user_count == 0:
            session.add(
                User(
                    username="user",
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
            "username": user.username,
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
            "username": user.username,
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


def create_user(username: str, email: str, password: str):
    with SessionLocal() as session:
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            secret_note="Secret note: only authenticated users can see this."
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user_to_dict(user)


def get_user_by_username(username: str):
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.username == username))
        return None if user is None else {"id": user.id, "username": user.username}


def update_user(user_id: int, username: str, email: str, password: str | None = None):
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            return None

        user.username = username
        user.email = email
        if password:
            user.password_hash = hash_password(password)
        session.commit()
        session.refresh(user)
        return user_to_dict(user)


def user_to_dict(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "password_hash": user.password_hash,
        "secret_note": user.secret_note,
        "created_at": user.created_at
    }
