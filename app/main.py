import os
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .database import (
    init_db, get_user_by_email, get_user_by_id, get_user_by_username,
    get_posts, get_post, create_post, create_user, update_user, hash_password,
    get_comments, create_comment,
)

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
API_BASE = "/api"
SECRET_KEY = "your secret key"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append({
            "поле": field,
            "message": f"Поле {field} обязательно к заполнению",
            "type": error["type"]
        })
    return JSONResponse(
        status_code=422,
        content={
            "error": "Ошибка валидации",
            "details": errors
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"HTTP {exc.status_code}",
            "message": exc.detail
        }
    )


def fmt_date(value):
    try:
        return value.strftime("%d.%m.%Y в %H:%M")
    except AttributeError:
        return str(value)


templates.env.filters["fmt_date"] = fmt_date
templates.env.globals["css_version"] = int((BASE_DIR / "static" / "style.css").stat().st_mtime)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "api_base": API_BASE,
            "is_authenticated": bool(request.session.get("user_id"))
        }
    )


@app.get("/login")
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/profile", status_code=303)

    return templates.TemplateResponse(
        name="login.html",
        request=request,
        context={"error": False, "api_base": API_BASE}
    )


@app.get("/register")
async def register_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/profile", status_code=303)
    return templates.TemplateResponse(
        name="register.html", request=request,
        context={"error": None, "api_base": API_BASE}
    )


def validate_account_data(username: str, email: str, password: str, password_required: bool = True):
    username = username.strip()
    email = email.strip().lower()
    if len(username) < 3 or len(username) > 32:
        return None, "Имя пользователя должно содержать от 3 до 32 символов."
    if not all(character.isalnum() or character in "_-" for character in username):
        return None, "Имя пользователя может содержать только буквы, цифры, «_» и «-»."
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return None, "Введите корректный адрес электронной почты."
    if (password_required or password) and len(password) < 6:
        return None, "Пароль должен содержать не менее 6 символов."
    return (username, email), None


@app.post("/register")
async def register(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    account_data, error = validate_account_data(username, email, password)
    if error:
        return templates.TemplateResponse(
            name="register.html", request=request,
            context={"error": error, "api_base": API_BASE}, status_code=400
        )

    username, email = account_data
    if get_user_by_username(username) or get_user_by_email(email):
        return templates.TemplateResponse(
            name="register.html", request=request,
            context={"error": "Пользователь с таким именем или почтой уже существует.", "api_base": API_BASE},
            status_code=409
        )

    user = create_user(username, email, password)
    request.session["user_id"] = user["id"]
    request.session["email"] = user["email"]
    return RedirectResponse(url="/profile", status_code=303)


@app.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = get_user_by_email(email.strip().lower())

    if not user or user["password_hash"] != hash_password(password):
        return templates.TemplateResponse(
            name="login.html",
            request=request,
            context={"error": True, "api_base": API_BASE},
            status_code=401
        )

    request.session["user_id"] = user["id"]
    request.session["email"] = user["email"]

    return RedirectResponse(url="/profile", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)


@app.get("/profile")
async def profile(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    user = get_user_by_id(request.session["user_id"])
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        name="profile.html", request=request,
        context={"api_base": API_BASE, "user": user, "error": None, "success": False}
    )


@app.post("/profile")
async def update_profile(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(""),
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    current_user = get_user_by_id(user_id)
    if not current_user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)

    account_data, error = validate_account_data(username, email, password, password_required=False)
    if error:
        return templates.TemplateResponse(
            name="profile.html", request=request,
            context={"api_base": API_BASE, "user": current_user, "error": error, "success": False},
            status_code=400
        )

    username, email = account_data
    username_owner = get_user_by_username(username)
    email_owner = get_user_by_email(email)
    if ((username_owner and username_owner["id"] != user_id) or
            (email_owner and email_owner["id"] != user_id)):
        return templates.TemplateResponse(
            name="profile.html", request=request,
            context={"api_base": API_BASE, "user": current_user, "error": "Имя пользователя или почта уже заняты.", "success": False},
            status_code=409
        )

    user = update_user(user_id, username, email, password or None)
    request.session["email"] = user["email"]
    return templates.TemplateResponse(
        name="profile.html", request=request,
        context={"api_base": API_BASE, "user": user, "error": None, "success": True}
    )


@app.get("/posts/new")
async def new_post_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        name="new_post.html", request=request,
        context={"api_base": API_BASE, "error": None}
    )


@app.post("/posts/new")
async def new_post(request: Request, title: str = Form(...), content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_by_id(user_id)
    clean_title = title.strip()
    clean_content = content.strip()
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    if not clean_title or not clean_content:
        return templates.TemplateResponse(
            name="new_post.html", request=request,
            context={"api_base": API_BASE, "error": "Заполните заголовок и текст публикации."},
            status_code=400
        )
    create_post(clean_title, clean_content, user["username"])
    return RedirectResponse(url="/", status_code=303)


@app.get("/posts/{post_id}")
async def post_detail(request: Request, post_id: int):
    post = get_post(post_id)
    if not post:
        return RedirectResponse(url="/", status_code=303)
    comments = get_comments(post_id)
    is_authenticated = bool(request.session.get("user_id"))
    return templates.TemplateResponse(
        name="post_detail.html", request=request,
        context={
            "api_base": API_BASE,
            "post": post,
            "comments": comments,
            "is_authenticated": is_authenticated,
            "error": None,
        }
    )


@app.post("/posts/{post_id}/comments")
async def add_comment(request: Request, post_id: int, content: str = Form(...)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_by_id(user_id)
    if not user:
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    post = get_post(post_id)
    if not post:
        return RedirectResponse(url="/", status_code=303)
    clean_content = content.strip()
    if not clean_content:
        comments = get_comments(post_id)
        return templates.TemplateResponse(
            name="post_detail.html", request=request,
            context={
                "api_base": API_BASE,
                "post": post,
                "comments": comments,
                "is_authenticated": True,
                "error": "Комментарий не может быть пустым.",
            },
            status_code=400,
        )
    create_comment(post_id, user["username"], clean_content)
    return RedirectResponse(url=f"/posts/{post_id}", status_code=303)


@app.get(API_BASE + "/health")
async def api_health():
    return {"status": "ok"}


@app.get(API_BASE + "/posts")
async def api_posts():
    return get_posts()


@app.post(API_BASE + "/posts")
async def api_create_post(request: Request, title: str = Form(...), content: str = Form(...)):
    user_id = request.session.get("user_id")

    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"}
        )

    user = get_user_by_id(user_id)

    if not user:
        request.session.clear()
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"}
        )

    clean_title = title.strip()
    clean_content = content.strip()

    if not clean_title or not clean_content:
        return JSONResponse(
            status_code=400,
            content={"detail": "Title and content cannot be empty"}
        )

    return create_post(clean_title, clean_content, user["username"])


@app.get(API_BASE + "/posts/{post_id}/comments")
async def api_comments(post_id: int):
    post = get_post(post_id)
    if not post:
        return JSONResponse(status_code=404, content={"detail": "Post not found"})
    return get_comments(post_id)


@app.post(API_BASE + "/posts/{post_id}/comments")
async def api_create_comment(
    request: Request, post_id: int, content: str = Form(...)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    user = get_user_by_id(user_id)
    if not user:
        request.session.clear()
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    post = get_post(post_id)
    if not post:
        return JSONResponse(status_code=404, content={"detail": "Post not found"})
    clean_content = content.strip()
    if not clean_content:
        return JSONResponse(status_code=400, content={"detail": "Comment cannot be empty"})
    return create_comment(post_id, user["username"], clean_content)


@app.get(API_BASE + "/profile")
async def api_profile(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"}
        )

    user = get_user_by_id(user_id)

    if not user:
        request.session.clear()
        return JSONResponse(
            status_code=401,
            content={"detail": "Not authenticated"}
        )

    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "created_at": str(user["created_at"]),
        "secret_note": user["secret_note"]
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
