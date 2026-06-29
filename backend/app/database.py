import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Grab the URL from the environment, defaulting to local SQLite if not found
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./omniscient.db")

# 2. Fix legacy URI formats (SQLAlchemy 1.4+ requires 'postgresql://', not 'postgres://')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Conditionally apply SQLite-only arguments
if DATABASE_URL.startswith("sqlite"):
    # Local development configuration
    engine = create_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # Production Supabase / PostgreSQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get the database session in our FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()