from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .database import init_db, get_user_by_email, get_user_by_id, get_posts, create_post, hash_password

BASE_DIR = Path(__file__).resolve().parent
API_BASE = "/api"
SECRET_KEY = "change-me"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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

    return templates.TemplateResponse(
        name="profile.html",
        request=request,
        context={"api_base": API_BASE}
    )


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

    return create_post(clean_title, clean_content, user["email"])


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
        "email": user["email"],
        "created_at": str(user["created_at"]),
        "secret_note": user["secret_note"]
    }