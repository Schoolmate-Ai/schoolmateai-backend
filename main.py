from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from services.user_management.controllers.super_admin_service import router as superadmin_router

app = FastAPI(title="SchoolMate AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "SchoolMate AI Backend is running ✅"}


app.include_router(superadmin_router)
