from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.conversation import router as conversation_router
from app.api.chat import router as chat_router
from app.core.exceptions import register_exception_handlers

app = FastAPI(
    title="Project Titan API",
    version="1.0.0",
)
register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(conversation_router)
app.include_router(chat_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Project Titan..  🚀"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "version": app.version,
    }