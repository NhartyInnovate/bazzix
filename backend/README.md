# ⚡ Bazzix

> Think Beyond.

Bazzix is a modern AI-powered workspace designed to help people think, create, research, analyze, and build faster.

Built with FastAPI, PostgreSQL, and Google's Gemini AI, Bazzix combines secure authentication, persistent conversations, intelligent AI interactions, and a scalable backend architecture to provide a production-ready foundation for next-generation AI applications.

Whether you're building an AI assistant, research platform, productivity tool, or enterprise AI solution, Bazzix is designed to scale with your vision.

---

# ✨ Features

## 🔐 Authentication

- Secure User Registration
- JWT Authentication
- OAuth2 Login
- Password Hashing
- Protected Endpoints

---

## 💬 Conversations

- Create Conversations
- Retrieve Conversations
- Rename Conversations
- Delete Conversations
- Automatically Generate Conversation Titles

---

## 🤖 AI Engine

- Google Gemini Integration
- Intelligent Context-Aware Responses
- Prompt Builder
- Modular AI Service Layer
- Automatic Conversation Memory

---

## 📝 Message History

- Store User Messages
- Store AI Responses
- Retrieve Complete Chat History
- Persistent Database Storage

---

## 🛡 Backend Engineering

- Layered Architecture
- SQLAlchemy ORM
- Alembic Database Migrations
- Global Exception Handling
- Health Monitoring Endpoint
- Environment-Based Configuration

---

# 🏗 Architecture

Bazzix follows a clean layered architecture designed for scalability and maintainability.

```

                Client
                   │
                   ▼
            FastAPI API Layer
                   │
                   ▼
            Business Services
                   │
                   ▼
               CRUD Layer
                   │
                   ▼
            PostgreSQL Database
                   │
                   ▼
              Google Gemini AI

```

Each layer has a single responsibility, making the project easier to maintain, test, and extend.

---

# 📂 Project Structure

```

app/

├── api/
│
├── core/
│
├── crud/
│
├── db/
│
├── models/
│
├── schemas/
│
├── services/
│
└── main.py

```

---

# 🚀 Tech Stack

### Backend

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Pydantic

### Authentication

- JWT
- OAuth2
- Password Hashing

### Artificial Intelligence

- Google Gemini API

### Development

- Python
- Uvicorn

---

# ⚙ Installation

Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/bazzix.git
```

Move into the project

```bash
cd bazzix
```

Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment

Windows

```bash
.venv\Scripts\activate
```

Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Variables

Create a `.env` file.

```env
DATABASE_URL=postgresql://username:password@localhost/bazzix

SECRET_KEY=your_secret_key

ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=30

GEMINI_API_KEY=your_gemini_api_key

GEMINI_MODEL=gemini-2.5-flash
```

---

# 🚀 Running the Project

```bash
uvicorn app.main:app --reload
```

Swagger Documentation

```
http://127.0.0.1:8000/docs
```

Health Endpoint

```
http://127.0.0.1:8000/health
```

---

# 📚 API Overview

## Authentication

- POST `/auth/register`
- POST `/auth/login`

## Users

- GET `/users/me`

## Conversations

- POST `/conversations`
- GET `/conversations`
- GET `/conversations/{id}`
- PATCH `/conversations/{id}`
- DELETE `/conversations/{id}`
- GET `/conversations/{id}/messages`

## Chat

- POST `/chat`

---

# 💡 Why Bazzix?

Bazzix is more than a chatbot backend.

It is the foundation for an intelligent workspace where users can think, research, write, analyze, code, and build with AI.

Designed with modularity in mind, Bazzix makes it easy to expand into document analysis, AI agents, financial intelligence, search, image understanding, voice interactions, and enterprise collaboration.

---

# 🛣 Roadmap

## Version 1.1

- Background AI Tasks
- Streaming Responses
- Token Usage Tracking
- Conversation Search
- Pagination
- Rate Limiting
- Improved Logging

## Version 2.0

- Document Intelligence
- Image Understanding
- AI Agents
- Voice Conversations
- Multiple AI Providers
- Enterprise Workspaces
- Real-Time Collaboration
- Web Search Integration

---

# 🤝 Contributing

Contributions are welcome.

If you have ideas, improvements, or bug fixes, feel free to fork the repository and submit a Pull Request.

---

# 📄 License

Licensed under the MIT License.

---

# 👨‍💻 Author

**Nathaniel Katugwa**

Computer Science Graduate

Backend Developer

AI Application Developer

GitHub:
https://github.com/YOUR_USERNAME

LinkedIn:
https://linkedin.com/in/YOUR_PROFILE

---

# 🌍 Vision

Our vision is to build an intelligent platform that empowers individuals, teams, and businesses to think faster, make better decisions, and create exceptional work with AI.

---

> **Bazzix**
>
> *Built for the way you think.*