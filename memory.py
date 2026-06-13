import os
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGO_URI)

checkpointer = MongoDBSaver(
    client=client,
    db_name="travel-planer-agent",
    collection_name="checkpoints"
)