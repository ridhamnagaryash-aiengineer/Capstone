# Capstone
HRMS Application for Capstone
# HR Assistant System (FastAPI + Gemini + Milvus + LangGraph)

AI-powered HR knowledge system with:

- HR Document Upload & Auto-Classification  
- Embedding Generation (Google Gemini Embeddings)  
- Vector Search (Milvus/Zilliz Cloud)  
- HR Assistant Chatbot with RAG  
- Role-based Authentication (Admin / Employee)  
- Chat History & Audit Logging  
- Local Document Storage  

---

## 🔧 Tech Stack

| Feature | Tech |
|--------|------|
| API | FastAPI |
| LLM | Google Gemini |
| Embeddings | `models/embedding-001` |
| Vector DB | Milvus / Zilliz Cloud |
| Workflow Engine | LangGraph |
| Auth | JWT (HS256) |
| DB | SQLite / PostgreSQL |
| ORM | SQLAlchemy |
| File Parsing | PyPDF2, python-docx |

---

## 📁 Project Structure

hr-system/
├── src/
│ ├── api/main.py
│ ├── agents/
│ ├── routes/
│ ├── services/
│ ├── models/
│ ├── schemas/
│ ├── vector_db/
│ ├── llm/
│ ├── core/
│ └── config/
├── uploads/
├── config/
│ ├── app_config.yaml
│ ├── model_config.yaml
│ └── prompt_templates.yaml
└── README.md

yaml
Copy code

---

# 🚀 Features Overview

## Admin Features
- Upload HR documents (PDF, DOCX, TXT)
- Auto content extraction
- Auto classification → `payroll` / `hr_policy` / `it_support` / `facilities`
- Auto chunking + embedding generation
- Store vectors in Milvus
- View and delete uploaded documents

## Employee Features
- Secure login
- HR chatbot with RAG-based answers
- Chat history stored per session

## Intelligence Pipeline
- LangGraph document workflow
- LangGraph query workflow
- Prompt templates loaded from YAML
- Gemini for classification, embeddings, and responses

---

# 🔐 Authentication & Authorization

JWT payload includes:

sub: user email (required)
email
role: "admin" | "employee"
grade
username
full_name

yaml
Copy code

## Role Rules

| Endpoint | Allowed |
|----------|---------|
| `/auth/*` | Public |
| `/admin/*` | Admin only |
| `/employee/*` | Employee or Admin |

Admins must be manually created or promoted.

---

# ⚙️ Environment Variables

Create `.env`:

SECRET_KEY=your-secret
DATABASE_URL=sqlite:///./hr_system.db

GEMINI_API_KEY=your_key_here

MILVUS_URI=<zilliz_cloud_uri>
MILVUS_API_KEY=<zilliz_key>

yaml
Copy code

---

# 📦 Installation & Running

### 1. Create virtual environment

python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate



### 2. Install dependencies

pip install -r requirements.txt


### 3. Create `.env`

cp .env.example .env



### 4. Run FastAPI server

uvicorn 
main:app 


API docs:

http://localhost:8001/docs

yaml
Copy code

---

# 📘 API Endpoints

## Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Create employee |
| POST | `/auth/login` | Login + JWT |
| GET | `/auth/me` | Get current user |

## Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/documents` | Upload HR document |
| GET | `/admin/documents` | List documents |
| DELETE | `/admin/documents/{file_id}` | Delete document |

## Employee
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/employee/chat` | Ask HR assistant |

---

# 🧠 Document Processing Pipeline

1. File uploaded  
2. Content extracted (PDF/DOCX/TXT)  
3. LangGraph workflow runs:
   - extract_content  
   - classify_document  
   - generate_embeddings  
4. Embeddings stored in Milvus  
5. DB updated with:
   - category  
   - confidence  
   - vector_count  

---

# 🗣️ Chat Pipeline

1. Query classified  
2. Embedding generated  
3. Milvus vector search performed  
4. Relevant chunks assembled  
5. Gemini generates final answer  
6. Message stored in DB with:
   - category  
   - confidence  
   - retrieved chunks  
   - sources  

---

# 🔍 Debugging Tips

### Check Milvus connection:
GET /health

yaml
Copy code

### Trace prompt templates:
Enable debug logs in `prompt_loader.py`.

### JWT fails?
Ensure `"sub"` exists and `"role"` is stored as string.

---

# 🤝 Contributing

PRs welcome.  
Use `black` + `isort` for formatting.

---

# 📄 License

Proprietary – internal use only.

