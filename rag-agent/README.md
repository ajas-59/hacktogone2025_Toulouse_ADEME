# 🤖 AI RAG Agents

## Document-Aware Assistants on n8n using Supabase, OpenAI and Anthropic Claude

![n8n + Supabase + OpenAI](https://img.shields.io/badge/Stack-n8n%20%7C%20Supabase%20%7C%20OpenAI-blue)
![Status](https://img.shields.io/badge/Prototype-Ready-green)
![Made with No-Code](https://img.shields.io/badge/Made%20with-No%20Code-brightgreen)

## 🧠 Part 1 - AI agent question/answering with Supabase RAG (ADEME documentation)

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


# 🚦 Part 2 — Transport Emissions AI Agent  
### *ImpactCO2 + n8n + Anthropic Claude*

![n8n Workflow](https://img.shields.io/badge/Workflow-n8n-yellow)
![CO₂ API](https://img.shields.io/badge/Data-ImpactCO2-orange)
![AI Model](https://img.shields.io/badge/Model-Anthropic%20Claude-blueviolet)

## 🧭 Overview

This workflow powers a **real-time AI assistant that analyzes transport-related CO₂ emissions**, using data from **ImpactCO2** and generating a friendly explanation through **Anthropic Claude**.

It turns raw emission values into a clear, contextualized message for end users:

- 🚗 Retrieves accurate carbon emissions for any transport mode  
- 📊 Classifies the environmental impact locally (via JS logic)  
- 🧠 Generates natural-language explanations with LLM reasoning  
- 🔄 Responds instantly through a webhook endpoint  

This demonstrates how **n8n can orchestrate APIs, custom analysis, and AI models** in a single automated workflow.

---

## 🗺️ Architecture

User Input

↓

Webhook Trigger
↓
ImpactCO2 API (HTTP Request)
↓
Local Analysis Engine (JS)
↓
Formatter (JS)
↓
Anthropic Claude (LLM Chain)
↓
Webhook Response


---

## 🧩 Node-by-Node Breakdown

### **1. Webhook (Trigger)**  
Receives user input via POST, typically including:

```json
{
  "distance_km": 12,
  "transport_mode": "bus_gnv"
}
```

### **2. HTTP Request — ImpactCO2 API**
Sends a GET request to:

https://impactco2.fr/api/transport/v1/<mode>

Returns official emissions data:

```json
{
  "value": 1.217,
  "unit": "kgCO2e",
  "label": "Bus (GNV)"
}
'''

### **3. Local Analysis Engine (JS Node)**
Performs domain-specific analysis such as:
carbon intensity classification
comparison to reference values
eco-score and interpretation
Example resulting object:
'''json
{
  "carbonIntensity": 1.217,
  "rating": "Moderate",
  "comparison": "631% of average car emissions (worse)",
  "recommendation": "Consider alternatives like tram or carpooling."
}
'''

### **4. Format Final Output (JS Node)**
Prepares stable, clean input for the LLM:
'''json
{
  "mode": "Bus (GNV)",
  "distance": 12,
  "analysis": { ... }
}
'''

5. Basic LLM Chain — Anthropic Claude
Generates a human-readable explanation including:
impact interpretation
comparison with other transport options
practical eco-friendly advice
Example output:
Your 12 km trip by Bus (GNV) emits 1.217 kg CO₂e, which is moderately high for this distance. Consider using electric public transport or carpooling when available.


6. Respond to Webhook
Returns the final AI-crafted message to the user:
'''json
{
  "message": "Your 12 km trip by Bus (GNV) emits 1.217 kg CO₂e... [etc]"
}
'''


## ✨ Features
✔ Live CO₂ emissions data from ImpactCO2
✔ Local rule-based carbon intensity analysis
✔ AI-generated explanations (Claude)
✔ Fully automated webhook endpoint
✔ Easily integratable into chat apps, Framer prototypes, or mobile apps


## 🎯 Goals
This project serves as a live, tangible demonstration of :

> Applied RAG principles in no-code

> AI automation in real workflows

> My ability to ship fast, useful AI tools

> My interest in AI agentic architectures, LLM orchestration & document intelligence
