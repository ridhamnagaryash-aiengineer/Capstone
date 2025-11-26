from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
load_dotenv()
database_url=os.getenv("DATABASE_URL")
connect_args = {}
engine_args = {}
# If SQLite → allow single-thread
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_args["connect_args"] = connect_args
else:
    # Postgres (Supabase) → standard pooling
    engine_args["pool_pre_ping"] = True

# Creating engine 
engine = create_engine(
    database_url,
    echo=os.getenv("DEBUG", "False").lower() == "true",
    **engine_args
)
# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# ORM base
Base = declarative_base()
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
