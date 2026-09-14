from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.core.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Персональный сайт с AI-ассистентом для представления профессиональных компетенций Андриса Янчевскиса",
    version="0.3.0",
)

# Подключение статических файлов
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Шаблонизатор Jinja2
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", summary="Главная страница")
async def index_page(request: Request):
    """Отображение главной страницы персонального сайта."""
    current_settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"settings": current_settings},
    )


# Подключение маршрутов API и health
app.include_router(router)
