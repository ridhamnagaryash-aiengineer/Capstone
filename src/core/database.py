# src/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Get database URL from environment or use SQLite default
database_url = os.getenv('DATABASE_URL', 'sqlite:///./hr_system.db')

# SQLite-specific configuration
connect_args = {}
if database_url.startswith('sqlite'):
    connect_args = {"check_same_thread": False}

# Create SQLAlchemy engine
engine = create_engine(
    database_url,
    connect_args=connect_args,
    poolclass=StaticPool if database_url.startswith('sqlite') else None,
    echo=os.getenv('DEBUG', 'False').lower() == 'true'
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

def get_db():
    """Dependency to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()