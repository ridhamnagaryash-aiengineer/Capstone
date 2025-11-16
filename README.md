🧠 HRMS AI Assistant — Intelligent HR Chat + Document RAG Pipeline
A Production-Grade HR Management System Powered by LLMs, Milvus Vector DB, and FastAPI

🚀 Overview
The HRMS AI Assistant is an enterprise-grade HR Management System that combines:

FastAPI for secure backend APIs
LiteLLM for unified LLM access (Gemini, OpenAI, Claude, Groq, etc.)
Milvus Vector Database for high-performance embedding storage
RAG engine for document-grounded HR responses
Role-based authentication for Admin and Employees
Automated Document Ingestion Pipeline (upload → extract → classify → chunk → embed → store)
LiveKit Integration for voice-based HR assistant interactions

This system enables:
✔ Employees to ask HR queries conversationally
✔ Admins to upload and manage HR documents
✔ Real-time semantic search from vector DB
✔ Automatic policy routing (payroll/hr/it/support/facilities)
✔ Persistent chat sessions
✔ Full monitoring & logging
✔ Voice-based interactions via LiveKit

🏗️ Features
🎯 Employee Features

Ask HR-related questions through an intelligent chat interface
Personalized responses based on JWT metadata (username, grade, role)
RAG-powered answers grounded in company HR documents
Follow-up questions with chat context
View chat history, rename sessions, delete sessions
Voice-based queries through LiveKit integration

🛠️ Admin Features

Upload HR documents (PDF/DOC/DOCX/TXT)
Automatic text extraction (PDF → plain text)
LLM-driven document classification
Smart chunking & embedding generation
Storage in category-specific Milvus collections
View documents with classification metadata
Delete documents (including Milvus vectors)

🤖 AI/LLM Features

Unified LLM interface via LiteLLM
Gemini / GPT / Claude support (switchable via env)
Safe fallback answers when no relevant vectors
Prompt templates loaded from YAML

🎙️ Voice Integration Features

LiveKit real-time voice communication
Voice-to-text HR query processing
Text-to-speech response delivery
Seamless integration with RAG pipeline
Natural conversation flow with voice agent

🗃️ Vector Database
Five Milvus collections:

hrms_hr_policy
hrms_payroll
hrms_it_support
hrms_facilities
hrms_uncategorized

Optimized for:

semantic search
category-level isolation
low latency


🧩 Project Architecture
hrms-ai-assistant/
│
├── config/
│   ├── app_config.yaml
│   ├── model_config.yaml
│   └── prompts_templates.yaml
│
├── src/
│   ├── agents/
│   │   ├── document_classifier_agent.py
│   │   └── query_router_agent.py
│   │
│   ├── core/
│   │   ├── database.py
│   │   └── security.py
│   │
│   ├── handlers/
│   │   └── error_handler.py
│   │
│   ├── llm/
│   │   └── lite_client.py   ← LiteLLM wrapper
│   │
│   ├── models/
│   │   ├── chat.py
│   │   ├── document.py
│   │   └── user.py
│   │
│   ├── prompt_engineering/
│   │   └── prompts_loader.py
│   │
│   ├── retriever/
│   │   └── hr_retriever.py
│   │
│   ├── routes/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   └── employee.py
│   │
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── document.py
│   │   └── user.py
│   │
│   ├── services/
│   │   ├── chat_service.py
│   │   ├── document_service.py
│   │   └── user_service.py
│   │
│   ├── utils/
│   │   ├── email.py
│   │   └── finduser.py
│   │
│   └── vector_db/
│       └── milvus_client.py
│
├── uploads/   ← Stored PDFs
├── create_admin.py
├── main.py
├── voice_agent.py
└── requirements.txt

🔌 System Architecture Diagram
          ┌───────────────────────────┐
          │         Employee          │
          └──────────────┬────────────┘
                         │
                ┌────────┴────────┐
                │                 │
                ▼                 ▼
      ┌──────────────────┐  ┌──────────────────┐
      │  Employee Route  │  │  LiveKit Voice   │
      └───────┬──────────┘  └────────┬─────────┘
              │                      │
              │                      ▼
              │            ┌──────────────────┐
              │            │  Voice Agent     │
              │            └────────┬─────────┘
              │                     │
              └──────────┬──────────┘
                         ▼
              ┌────────────────────┐
              │    Chat Service    │
              └─────────┬──────────┘
                        │
                        ▼
             ┌──────────────────────┐
             │ Query Router Agent   │
             └──────┬──────────────┘
                    │
        ┌────────────────────┐
        │  LiteLLM Client    │
        └──────┬────────────┘
               │
               ▼
       ┌───────────────────────┐
       │   Vector Retriever     │
       └─────────┬─────────────┘
                 │
                 ▼
      ┌───────────────────────────┐
      │     Milvus Vector DB      │
      └───────────────────────────┘

📥 Document Ingestion Pipeline
Admin → Upload Document
        │
        ▼
[DocumentService]
1. Validate file
2. Extract content (PDF → text)
3. Classify via LLM
4. Normalize category
5. Chunk text
6. Generate embeddings
7. Store vectors into Milvus category collection
8. Update DB metadata

🔧 Setup Instructions
1️⃣ Clone repository
bashgit clone https://github.com/your-repo/hrms-ai-assistant.git
cd hrms-ai-assistant
2️⃣ Create virtual environment (Anaconda)
bashconda create -n hrms python=3.10 -y
conda activate hrms
3️⃣ Install dependencies
bashpip install -r requirements.txt
4️⃣ Configure environment variables
Create .env:
bash# LLM Keys (Gemini / GPT / Claude supported)
GEMINI_API_KEY=xxxxxxxxxxxx

# LiteLLM model routing
LLM_MODEL=gemini/gemini-1.5-flash
EMBED_MODEL=gemini/text-embedding-004

# Milvus
MILVUS_URI=https://example.api.zillizcloud.com
MILVUS_API_KEY=xxxxxxxxxxxx

# JWT
SECRET_KEY=supersecretkey
ALGORITHM=HS256

# DB
DATABASE_URL=sqlite:///./hr_system.db
5️⃣ Start Server
bashuvicorn main:app --reload

🔐 Authentication
Roles

admin
employee

JWT Payload Includes

email
username
full_name
grade
role

Admin-only routes:

/admin/documents

Employee-only:

/employee/chat


📚 API Documentation
After running server:
👉 Swagger UI
http://localhost:8000/docs
👉 ReDoc
http://localhost:8000/redoc

💬 Chat Workflow
Request
httpPOST /employee/chat
Authorization: Bearer <token>

{
  "message": "What is the leave policy?",
  "session_id": null
}
Response
json{
  "session_id": "uuid-1234",
  "response": "Based on policy...",
  "sources": [...],
  "category": "hr_policy",
  "confidence": 0.95
}

🗄️ Document Workflow
Upload Document
httpPOST /admin/documents
file: <PDF>
Response
json{
  "id": 1,
  "file_id": "uuid",
  "category": "payroll",
  "vector_count": 23,
  "processing_status": "completed"
}

🧠 RAG Architecture
Query classification:

LLM categorizes user question
Normalized to one of:

hr_policy
payroll
it_support
facilities
uncategorized



Semantic Search:

Query embedding via LiteLLM
Search within single Milvus category collection
Retrieve top-k chunks
Feed to LLM with context

Fallback:

If no chunks:

LLM uses internal HR knowledgebase template




🔍 Milvus Schema
Each collection stores:
FieldTypePurposeidint64Vector IDfile_idstringDocument IDfilenamestringOriginal filenamechunk_indexintChunk numbercategorystringNormalized categorytextstringChunk textembeddingfloat vector768-dim embedding

🧩 LiteLLM Integration
LiteLLM provides:

provider-agnostic API
automatic key loading (GEMINI_API_KEY)
same interface for GPT, Claude, Gemini
future-proof model switching

Used for:

Chat completions
Embedding generation
Model routing via YAML or .env


🛡️ Security
✔ JWT Authentication
✔ Role-based access control
✔ Safe file uploads
✔ SQLAlchemy ORM protection
✔ No hardcoded keys
✔ Config in environment + YAML

🧪 Testing
bashpytest -q
Unit tests for:

document extraction
chunking
LLM classification
embedding generation
Milvus search behavior


📈 Performance Considerations

Collections isolated per category → faster search
Chunk size 1000, stride 800 → optimal for HR policy text
IVF_FLAT or HNSW indexing recommended
LiteLLM caching optional
Lazy loading for classifier prompts


🧭 Future Enhancements

Admin UI for editing classifications
Automatic document re-processing
Reranking model (Cross encoder)
Hybrid search (keyword + vector)
Reinforcement-based answer optimization


🏁 Conclusion
This project is a fully production-ready HRMS AI backend, combining:

intelligent document understanding
stateful chat assistant
high-performance vector search
modular architecture
enterprise security