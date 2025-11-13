# scripts/create_admin.py
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.models.user import User, UserRole
from src.core.security import get_password_hash
from src.core.database import Base, engine
from src.models import chat

Base.metadata.create_all(bind=engine)



def create_admin():
    db: Session = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(User).filter(User.email == "admin@gmail.com").first()
        if admin:
            print("⚠️ Admin already exists.")
            return

        # Create admin user
        admin = User(
            email="admin@gmail.com",
            username="admin",
            full_name="HR Manager",
            hashed_password=get_password_hash("admin@123"),  # you can change this
            grade="Admin",
            role=UserRole.ADMIN,
            is_active=True
        )

        db.add(admin)
        db.commit()

        print("✅ Admin user created successfully")
        print("Email: admin@gmail.com")
        print("Password: admin@123")
        print("⚠️ CHANGE THE PASSWORD IMMEDIATELY!")
    except Exception as e:
        print(f"❌ Failed to create admin: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
