from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from services.user_management.controllers.super_admin_service import router as superadmin_router
from services.user_management.controllers.school_service import router as school_router
from services.user_management.controllers.subject_service import router as subject_router


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
app.include_router(school_router)
app.include_router(subject_router)
