from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from datetime import datetime

app = FastAPI(title="MedLex API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "medlex_dictionary")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
terms_collection = db["medical_terms"]
phrases_collection = db["phrases"]

class ExampleSentence(BaseModel):
    german: str
    kurdish: str

class MedicalTermCreate(BaseModel):
    german: str
    kurdish: str
    pronunciationDe: Optional[str] = None
    pronunciationKu: Optional[str] = None
    category: str
    example: Optional[ExampleSentence] = None
    relatedTerms: Optional[List[str]] = []

def term_helper(term) -> dict:
    return {
        "id": str(term["_id"]),
        "german": term["german"],
        "kurdish": term["kurdish"],
        "pronunciationDe": term.get("pronunciationDe"),
        "pronunciationKu": term.get("pronunciationKu"),
        "category": term["category"],
        "example": term.get("example"),
        "relatedTerms": term.get("relatedTerms", []),
    }

def phrase_helper(phrase) -> dict:
    return {
        "id": str(phrase["_id"]),
        "german": phrase["german"],
        "kurdish": phrase["kurdish"],
        "context": phrase["context"],
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "MedLex API"}

@app.get("/api/terms")
async def get_all_terms(category: Optional[str] = None, search: Optional[str] = None):
    query = {}
    if category and category != "all":
        query["category"] = category
    if search:
        query["$or"] = [
            {"german": {"$regex": search, "$options": "i"}},
            {"kurdish": {"$regex": search, "$options": "i"}},
        ]
    terms = []
    cursor = terms_collection.find(query).sort("german", 1)
    async for term in cursor:
        terms.append(term_helper(term))
    return terms

@app.get("/api/terms/{term_id}")
async def get_term(term_id: str):
    term = await terms_collection.find_one({"_id": ObjectId(term_id)})
    if not term:
        raise HTTPException(status_code=404, detail="Term not found")
    return term_helper(term)

@app.post("/api/terms")
async def create_term(term: MedicalTermCreate):
    term_dict = term.model_dump()
    term_dict["createdAt"] = datetime.utcnow()
    term_dict["updatedAt"] = datetime.utcnow()
    result = await terms_collection.insert_one(term_dict)
    created_term = await terms_collection.find_one({"_id": result.inserted_id})
    return term_helper(created_term)

@app.put("/api/terms/{term_id}")
async def update_term(term_id: str, term_update: dict):
    term_update["updatedAt"] = datetime.utcnow()
    await terms_collection.update_one({"_id": ObjectId(term_id)}, {"$set": term_update})
    updated_term = await terms_collection.find_one({"_id": ObjectId(term_id)})
    return term_helper(updated_term)

@app.delete("/api/terms/{term_id}")
async def delete_term(term_id: str):
    await terms_collection.delete_one({"_id": ObjectId(term_id)})
    return {"message": "Term deleted"}

@app.get("/api/phrases")
async def get_all_phrases():
    phrases = []
    cursor = phrases_collection.find({})
    async for phrase in cursor:
        phrases.append(phrase_helper(phrase))
    return phrases

@app.post("/api/phrases")
async def create_phrase(phrase: dict):
    result = await phrases_collection.insert_one(phrase)
    created = await phrases_collection.find_one({"_id": result.inserted_id})
    return phrase_helper(created)

@app.get("/api/stats")
async def get_stats():
    total_terms = await terms_collection.count_documents({})
    total_phrases = await phrases_collection.count_documents({})
    return {"totalTerms": total_terms, "totalPhrases": total_phrases, "categories": 6}

@app.get("/api/categories")
async def get_categories():
    return [
        {"id": "all", "name": "Alle", "nameKu": "Hemû", "icon": "Grid3X3"},
        {"id": "anatomy", "name": "Anatomie", "nameKu": "Anatomî", "icon": "Bone"},
        {"id": "symptoms", "name": "Symptome", "nameKu": "Nîşan", "icon": "Thermometer"},
        {"id": "diseases", "name": "Krankheiten", "nameKu": "Nexweşî", "icon": "Activity"},
        {"id": "medications", "name": "Medikamente", "nameKu": "Derman", "icon": "Pill"},
        {"id": "procedures", "name": "Verfahren", "nameKu": "Prosedar", "icon": "Stethoscope"},
        {"id": "emergency", "name": "Notfall", "nameKu": "Awarte", "icon": "Siren"},
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
