# main.py
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="SchoolMate AI Backend")

# Optional: Add CORS if you want frontend access during dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to frontend URL in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "SchoolMate AI Backend is running ✅"}


from services.user_management.api.super_admin_router import router as superadmin_router
app.include_router(superadmin_router)
