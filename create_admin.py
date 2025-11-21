# scripts/create_admin.py
from sqlalchemy.orm import Session
from src.core.database import SessionLocal, Base, engine
from src.core.security import get_password_hash
from src.models.user import User
from src.models.chat import ChatSession, ChatMessage

Base.metadata.create_all(bind=engine)


def create_admin():
    db: Session = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "admin@gmail.com").first()
        if admin:
            print("⚠️ Admin already exists.")
            return

        admin = User(
            email="admin@gmail.com",
            username="admin",
            full_name="HR Manager",
            hashed_password=get_password_hash("admin@123"),
            grade="Admin",
            role='admin',
            is_active=True
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("✅ Admin user created successfully")
        print(f"ID: {admin.id}")
        print("Email: admin@gmail.com")
        print("Password: admin@123")
        print("⚠️ CHANGE THE PASSWORD IMMEDIATELY!")
        
    except Exception as e:
        print(f"❌ Failed to create admin: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
