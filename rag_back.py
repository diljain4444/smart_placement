from langgraph.checkpoint.memory import InMemorySaver
from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from dotenv import load_dotenv  
from typing import Annotated
from langgraph.graph import add_messages
from langchain_community.document_loaders import (
    PyPDFLoader,
    PyMuPDFLoader,
    Docx2txtLoader,
    CSVLoader,
    TextLoader,
    WebBaseLoader,
    UnstructuredImageLoader,
    UnstructuredPDFLoader
)
load_dotenv()
import re
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Any, Dict
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_community.retrievers import BM25Retriever
from langgraph.graph import StateGraph, END, START
from typing import TypedDict
import time
from langchain_groq import ChatGroq
import os
# =============================    LLM CALLS ======================================

# LLM for query expansion — moderate temperature is OK here (creative rephrasing)
model_query = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.4,
)

# LLM for answer generation — LOW temperature to prevent hallucination
model_answer = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1,   # near-deterministic: stick to facts in context
)

# Keep backward-compat alias used elsewhere
model_text = model_query
embedding = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

#========================    TEXT INGESTION =================================================

def ingestion(path):
    file_type = path.split(".")[-1].lower()
    if file_type == "pdf":
        loader = PyMuPDFLoader(path)
        documents = loader.load()
    elif file_type == "docx":
        loader = Docx2txtLoader(path)
        documents = loader.load()
    elif file_type == "csv":
        loader = CSVLoader(path)
        documents = loader.load()
    elif file_type == "txt":
        loader = TextLoader(path)
        documents = loader.load()
    elif file_type in ["png", "jpg", "jpeg"]:
        loader = UnstructuredImageLoader(path)
        documents = loader.load()
    elif file_type == "ocr":
        loader = UnstructuredPDFLoader(path)
        documents = loader.load()
    elif path.startswith("http"):
        loader = WebBaseLoader(path)
        documents = loader.load()
    else:
        raise ValueError("Unsupported file format")
    return documents

#=======================     CLEANING ====================================================

def cleaning(documents):
    cleaned_docs = []
    for doc in documents:
        text = doc.page_content
        text = re.sub(r'Page\s+\d+', ' ', text)
        text = re.sub(r'^\s*\d+\s*$', ' ', text, flags=re.MULTILINE)
        text = re.sub(r'[^\x00-\x7F]+', ' ', text)
        # Preserve paragraph breaks but collapse excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
        if text:   # skip empty docs
            cleaned_docs.append(
                Document(
                    page_content=text,
                    metadata=doc.metadata
                )
            )
    return cleaned_docs

#=======================     PREPROCESS =========================

def preprocess(path):
    docs = ingestion(path=path)
    clean_text = cleaning(docs)
    # FIX: Larger chunks (500) preserve more context per chunk, reducing
    # fragmentation that causes the LLM to hallucinate missing pieces.
    # Overlap of 100 ensures sentences at chunk boundaries aren't lost.
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    splitted_doc = splitter.split_documents(clean_text)
    return splitted_doc

#===================== STATE CREATION =============================

class state(TypedDict):
    query: str
    multi_queries_result: List[str]
    merged_docs: List[Dict]
    reranked: List[Dict]
    retriever: Any
    bm25: Any
    context: str
    answer: str

# ===================== MULTI QUERY ==========================

class QueryList(BaseModel):
    queries: List[str] = Field(description="List of exactly 3 search queries")

parser = PydanticOutputParser(pydantic_object=QueryList)

def multi_query(question):
    prompt = PromptTemplate(
        template="""\
You are a query expansion assistant for a document retrieval system.

Your job is to rephrase the user's question into exactly 3 different search
queries that will help retrieve the most relevant passages from the document.

RULES:
- Each query must stay closely related to the original question.
- Do NOT add topics or concepts that the user did not mention.
- Use different wording/phrasing but keep the same intent.
- Keep queries concise (under 20 words each).

Question: {question}

{format_instructions}
""",
        input_variables=["question"],
        partial_variables={
            "format_instructions": parser.get_format_instructions()
        },
    )
    chain = prompt | model_query | parser
    result = chain.invoke({"question": question})
    return result.queries

#======================    HYBRID SEARCH     ====================

def hybrid_search(state, query):
    all_docs = []
    retriever = state["retriever"]
    bm25_retrive = state["bm25"]

    vector_docs = retriever.invoke(query)
    for doc in vector_docs:
        all_docs.append({"doc": doc, "retriver": "vector", "query": query})

    bm25_docs = bm25_retrive.invoke(query)
    for doc in bm25_docs:
        all_docs.append({"doc": doc, "retriver": "bm25", "query": query})

    return all_docs

#=====================     MULTI QUERY RETRIEVAL ==========================

def multi_query_retrival(state):
    query = state["query"]
    docs = []
    queries = multi_query(query)
    for que in queries:
        res = hybrid_search(state, que)
        docs.extend(res)
    return {"multi_queries_result": docs}

# =========================  MERGE DOCS ========================

def merging(state):
    docs = state["multi_queries_result"]
    merged = {}
    for item in docs:
        doc = item["doc"]
        query = item["query"]
        retriver = item["retriver"]
        doc_id = hash(doc.page_content)
        if doc_id not in merged:
            merged[doc_id] = {
                "doc": doc,
                "query": set(),
                "retriver": set(),
                "count": 0
            }
        merged[doc_id]["query"].add(query)
        merged[doc_id]["retriver"].add(retriver)
        merged[doc_id]["count"] += 1
    return {"merged_docs": list(merged.values())}

# ======================== RE-RANKING =================================

def re_ranking(state):
    reranked = []
    docs = state["merged_docs"]
    for item in docs:
        score = 0
        score += item["count"] * 2
        score += 3 if len(item["retriver"]) > 1 else 1
        score += len(item["query"])
        reranked.append({
            "doc": item["doc"],
            "score": score,
            "meta_info": {
                "query": item["query"],
                "retriver": item["retriver"],
                "count": item["count"]
            }
        })
    final = sorted(reranked, key=lambda x: x["score"], reverse=True)
    return {"reranked": final}

#============================ CONTEXT ==================================

def context_builder(state):
    docs = state["reranked"]
    # FIX: Use top 5 chunks instead of 3 — gives the LLM more evidence
    # to work with, reducing the need to "fill in" missing information.
    context_list = docs[:5]
    # FIX: Number each chunk so the answer prompt can reference them
    # and the LLM understands these are separate evidence passages.
    numbered = []
    for i, item in enumerate(context_list, 1):
        numbered.append(f"[Source {i}]:\n{item['doc'].page_content}")
    return {"context": "\n\n".join(numbered)}

#=========================== ANSWER =========================================

strparser = StrOutputParser()

def answer_generator(state):
    query = state["query"]
    context = state["context"]
    prompt = PromptTemplate(
        template="""\
You are a precise document Q&A assistant. Your ONLY job is to answer
the user's question using EXCLUSIVELY the information provided in the
context passages below.

=== STRICT RULES (you MUST follow ALL of these) ===

1. ONLY use facts, numbers, names, and details that are EXPLICITLY
   stated in the context passages below. Do NOT add any outside
   knowledge, assumptions, or inferences.

2. If the context does not contain enough information to answer the
   question, respond EXACTLY with:
   "This information is not available in the uploaded document."

3. When answering, mentally check each claim you make — if you cannot
   point to the specific source passage that supports it, DELETE that
   claim from your answer.

4. Use direct quotes from the context where appropriate to support
   your answer.

5. Keep your answer well-structured:
   - Start with a brief direct answer (1-2 sentences).
   - Then provide supporting details from the context if needed.
   - Use bullet points for multiple pieces of information.

6. Do NOT begin your answer with phrases like "Based on the context"
   or "According to the document". Just answer directly.

7. Do NOT hallucinate, speculate, or make up any information.
   When in doubt, say you don't have enough information.

=== CONTEXT PASSAGES ===

{context}

=== USER QUESTION ===

{query}

=== YOUR ANSWER ===
""",
        input_variables=["query", "context"]
    )
    # FIX: Use the dedicated low-temperature model for answer generation
    chain = prompt | model_answer | strparser
    result = chain.invoke({"query": query, "context": context})
    # Strip any trailing whitespace or artifacts
    return {"answer": result.strip()}

#===============================  GRAPH CREATION ============================

graph = StateGraph(state)

graph.add_node("multi_query_retrival", multi_query_retrival)
graph.add_node("merging", merging)
graph.add_node("re_ranking", re_ranking)
graph.add_node("context_builder", context_builder)
graph.add_node("answer_generator", answer_generator)

graph.add_edge(START, "multi_query_retrival")
graph.add_edge("multi_query_retrival", "merging")
graph.add_edge("merging", "re_ranking")
graph.add_edge("re_ranking", "context_builder")
graph.add_edge("context_builder", "answer_generator")

workflow = graph.compile()