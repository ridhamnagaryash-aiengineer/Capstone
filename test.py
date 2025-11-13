from src.core.database import Base, engine
from src.models import chat
Base.metadata.create_all(bind=engine)
exit()
