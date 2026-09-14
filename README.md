## Установка и запуск
```bash
python -m pip install fastapi "uvicorn[standart] sqlalchemy jinja2 python-multipart"
python -m uvicorn app.main:app --reload

http://127.0.0.1:8000/
```