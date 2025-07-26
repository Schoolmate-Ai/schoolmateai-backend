from shared.db import engine, Base # adjust as per your structure
       # import all models

def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    reset_db()
