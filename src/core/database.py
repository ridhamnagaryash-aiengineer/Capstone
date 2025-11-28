from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

# Load environment variables
load_dotenv()

# Get database configuration from environment
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")

# Construct database URL
if all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
    # URL encode password to handle special characters
    encoded_password = quote_plus(DB_PASSWORD)
    # For PostgreSQL - construct proper connection string
    database_url = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    # Fallback to DATABASE_URL if individual components not provided
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError(
            "Database configuration is incomplete. Please set DB_HOST, DB_NAME, "
            "DB_USER, DB_PASSWORD in .env file or provide DATABASE_URL"
        )

# Configure connection arguments based on database type
connect_args = {}
engine_args = {}

if database_url.startswith("sqlite"):
    # SQLite configuration
    connect_args = {"check_same_thread": False}
    engine_args["connect_args"] = connect_args
else:
    # PostgreSQL/Supabase configuration
    engine_args["pool_pre_ping"] = True
    engine_args["pool_size"] = 5
    engine_args["max_overflow"] = 10
    engine_args["pool_recycle"] = 3600  # Recycle connections after 1 hour

# Create engine
try:
    engine = create_engine(
        database_url,
        echo=os.getenv("DEBUG", "False").lower() == "true",
        **engine_args
    )
    # Test connection
    with engine.connect() as conn:
        print("✓ Database connection successful!")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    print(f"Connection string format: postgresql://USER:PASSWORD@HOST:PORT/DATABASE")
    print(f"Your config: DB_HOST={DB_HOST}, DB_PORT={DB_PORT}, DB_NAME={DB_NAME}, DB_USER={DB_USER}")
    raise

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM base
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()