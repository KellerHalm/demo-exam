## Установка и запуск
```bash
python -m pip install fastapi "uvicorn[standard] sqlalchemy jinja2 python-multipart python-dotenv"
cp .env.example .env
python -m app.main

http://127.0.0.1:8000/
```

Адрес и порт задаются в файле `.env` (HOST, PORT). Первого пользователя создайте самостоятельно через форму регистрации.