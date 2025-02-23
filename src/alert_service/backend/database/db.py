from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base
from termcolor import cprint

DATABASE_URL = "sqlite:///./alerts.db"  # SQLite database file

# The connect_args are needed for SQLite
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    cprint("DB initialization successful!", "green")
