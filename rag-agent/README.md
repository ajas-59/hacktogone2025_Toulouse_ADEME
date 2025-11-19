# 🤖 AI RAG Agent — Document-Aware Assistant with n8n + Supabase + OpenAI

![n8n + Supabase + OpenAI](https://img.shields.io/badge/Stack-n8n%20%7C%20Supabase%20%7C%20OpenAI-blue)
![Status](https://img.shields.io/badge/Prototype-Ready-green)
![Made with No-Code](https://img.shields.io/badge/Made%20with-No%20Code-brightgreen)

## 🧠 Project Description

This project is a **RAG-based intelligent assistant** (Retrieval-Augmented Generation) built with **no-code tools**.  
It allows an AI agent to answer questions based on **your own documents**, such as PDFs or Google Docs.

> ✅ You ask a question  
> 📚 The agent searches through a vector database of your documents  
> 🧾 It finds the most relevant chunks  
> 🤖 It responds with a personalized, context-aware answer

The assistant is deployable as a **public web chat** (via n8n) or embedded into a site (via **Framer** or other tools).

---

## 🚀 Stack & Tools

| Component | Tool |
|----------|------|
| Automation Workflow | [n8n](https://n8n.io) |
| Vector Store | [Supabase](https://supabase.com) + `pgvector` |
| Embedding Model | OpenAI `text-embedding-3-small` |
| Chat Model | OpenAI GPT-4.1 |
| Document Ingestion | Google Drive → n8n |
| UI (optional) | [Framer](https://framer.com) |

---

## 📁 How It Works

### 🟦 1. Document Ingestion Pipeline (one-time)

- Download file from Google Drive
- Extract content (PDF, Doc, etc.)
- Split into chunks (Recursive Text Splitter)
- Generate embeddings (OpenAI)
- Store in Supabase `documents` table (with metadata + vector)

### 🟨 2. Chat Agent Workflow (on message)

- User asks a question
- AI Agent generates question embedding
- Performs vector search in Supabase
- Retrieves top-matching chunks
- Generates a final answer with context

---

## ✨ Features

- ✅ No-code document ingestion pipeline
- ✅ AI agent aware of custom knowledge base
- ✅ Supabase vector search with `pgvector`
- ✅ Real-time chat deployment (public or embedded)
- ✅ Google Drive integration for dynamic ingestion

---

## 📺 Demo (Framer site or n8n public chat)

> 💬 Try the agent live:  
> [https://your-framer-url.com](https://your-framer-url.com)  
> or  
> [https://n8n.cloud/chat/your-agent](https://n8n.cloud/chat/your-agent)

---

## 📌 Use Case Examples

- Internal knowledge assistant for a training center or company
- Smart FAQ based on documentation
- Sales playbook assistant
- CV bot: turn your resume into a chatbot
- Educational assistant for course content

---

## ⚡ Quick Setup (for reproducibility)

1. Clone this repo
2. Create a project on [Supabase](https://supabase.com)
3. Create the `documents` table with pgvector:
   ```sql
   create extension if not exists vector;
   create table documents (
     id bigserial primary key,
     content text,
     metadata jsonb,
     embedding vector(1536)
   );
