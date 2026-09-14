```bash
python -m pip install fastapi "uvicorn[standart] sqlalchemy jinja2 python-multipart"
python -m uvicorn app.main:app --reload
```