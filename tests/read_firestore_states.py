import os
import sys
import pickle
from google.cloud import firestore

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

db = firestore.Client()
print("Collections in Firestore:")
for col in db.collections():
    print(f"- Collection: {col.id}")

print("\nDocuments in agent_states:")
docs = list(db.collection("agent_states").list_documents())
for doc in docs:
    print(f"- Doc ID: {doc.id}")
    checkpoints = list(doc.collection("checkpoints").get())
    print(f"  Checkpoints count: {len(checkpoints)}")
    for cp in checkpoints:
        cp_data = cp.to_dict()
        checkpoint = pickle.loads(cp_data["checkpoint"])
        print(f"    Checkpoint ID: {cp.id}")
        print(f"    Created At: {cp_data.get('created_at')}")
        print(f"    Messages count: {len(checkpoint['channel_values'].get('messages', []))}")
        for msg in checkpoint['channel_values'].get('messages', []):
            print(f"      {msg.__class__.__name__}: {msg.content[:40]}")
