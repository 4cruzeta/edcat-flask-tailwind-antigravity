import pickle
import logging
from typing import Any, Dict, List, Optional, Tuple, Sequence, Iterator

from google.cloud import firestore
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata, CheckpointTuple

logger = logging.getLogger("edcat.persistence")

class FirestoreCheckpointer(BaseCheckpointSaver):
    """
    Implementação avançada de Checkpointer do LangGraph usando Firestore.
    Adere ao padrão incremental do LangGraph 0.2+ / 0.3+, salvando canais
    separadamente na subcoleção 'blobs' de forma resiliente e stateless.
    """
    def __init__(self, collection_name: str = "agent_states"):
        super().__init__()
        self.db = firestore.Client()
        self.collection = self.db.collection(collection_name)

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Recupera o estado (Checkpoint) para uma dada configuração (thread_id)."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if checkpoint_id:
            doc = self.collection.document(thread_id).collection("checkpoints").document(checkpoint_id).get()
        else:
            # Busca o checkpoint mais recente
            docs = self.collection.document(thread_id).collection("checkpoints").order_by(
                "created_at", direction=firestore.Query.DESCENDING
            ).limit(1).get()
            doc = docs[0] if docs else None

        if doc and doc.exists:
            data = doc.to_dict()
            checkpoint = pickle.loads(data["checkpoint"])
            
            # Carrega metadados (defensivo contra formatos de legado)
            metadata_raw = data.get("metadata")
            if isinstance(metadata_raw, bytes):
                metadata = pickle.loads(metadata_raw)
            else:
                metadata = metadata_raw or {}
                
            parent_id = data.get("parent_id")
            
            # 1. Carrega incrementalmente os blobs das versões indicadas no checkpoint
            versions = checkpoint.get("channel_versions", {})
            channel_values = {}
            
            if versions:
                blobs_ref = self.collection.document(thread_id).collection("blobs")
                doc_refs = [blobs_ref.document(f"{checkpoint_ns}::{k}::{v}") for k, v in versions.items()]
                
                # Executa get_all para puxar tudo em uma única viagem HTTP (Performance!)
                blob_docs = self.db.get_all(doc_refs)
                for blob_doc in blob_docs:
                    if blob_doc.exists:
                        blob_data = blob_doc.to_dict()
                        type_str = blob_data.get("type")
                        bytes_data = blob_data.get("data")
                        
                        # Extrai o nome do canal a partir do doc_id estruturado (ns::canal::versao)
                        parts = blob_doc.id.split("::")
                        if len(parts) >= 2:
                            channel_name = parts[-2]
                            if type_str != "empty":
                                channel_values[channel_name] = self.serde.loads_typed((type_str, bytes_data))
            
            checkpoint["channel_values"] = channel_values
            
            # 2. Carrega as escritas pendentes (pending_writes)
            writes = []
            writes_docs = self.collection.document(thread_id).collection("writes").where(filter=firestore.FieldFilter("checkpoint_id", "==", doc.id)).get()
            for w_doc in writes_docs:
                w_data = w_doc.to_dict()
                w_type = w_data.get("type", "pickle")
                w_raw = w_data.get("value")
                if w_type == "pickle":
                    w_val = pickle.loads(w_raw)
                else:
                    w_val = self.serde.loads_typed((w_type, w_raw))
                writes.append((w_data.get("task_id"), w_data.get("channel"), w_val))
            
            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": doc.id
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
                pending_writes=writes,
                parent_config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": parent_id}} if parent_id else None
            )
        return None

    def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> Dict[str, Any]:
        """Salva um novo estado (Checkpoint) no Firestore."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        
        # 1. Copia o checkpoint e extrai os valores dos canais (channel_values)
        c = checkpoint.copy()
        values = c.pop("channel_values", {})
        
        # Cria um batch do Firestore para atomicidade e velocidade
        batch = self.db.batch()
        
        # 2. Grava os novos blobs de versão na subcoleção correspondente
        blobs_ref = self.collection.document(thread_id).collection("blobs")
        for k, v in new_versions.items():
            doc_id = f"{checkpoint_ns}::{k}::{v}"
            if k in values:
                type_str, bytes_data = self.serde.dumps_typed(values[k])
            else:
                type_str, bytes_data = "empty", b""
            
            doc_ref = blobs_ref.document(doc_id)
            batch.set(doc_ref, {
                "type": type_str,
                "data": bytes_data
            })
            
        # 3. Grava o cabeçalho/metadado do checkpoint (sem o peso de channel_values)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        cp_ref = self.collection.document(thread_id).collection("checkpoints").document(checkpoint_id)
        batch.set(cp_ref, {
            "checkpoint": pickle.dumps(c),
            "metadata": pickle.dumps(metadata),
            "created_at": now,
            "parent_id": config["configurable"].get("checkpoint_id")
        })
        
        # Submete todas as alterações de uma vez
        batch.commit()
        logger.info(f"[Persistence] Checkpoint {checkpoint_id} e blobs gravados com sucesso no Firestore.")
        
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id
            }
        }

    def put_writes(self, config: Dict[str, Any], writes: Sequence[Tuple[str, Any]], task_id: str) -> None:
        """Salva as escritas intermediárias no Firestore (essencial para concorrência)."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        
        batch = self.db.batch()
        
        for idx, (channel, value) in enumerate(writes):
            doc_id = f"{checkpoint_id}_{task_id}_{idx}"
            doc_ref = self.collection.document(thread_id).collection("writes").document(doc_id)
            
            type_str, bytes_data = self.serde.dumps_typed(value)
            
            batch.set(doc_ref, {
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "channel": channel,
                "type": type_str,
                "value": bytes_data,
                "created_at": firestore.SERVER_TIMESTAMP
            })
            
        batch.commit()

    def list(self, config: Optional[Dict[str, Any]], *, filter: Optional[Dict[str, Any]] = None, before: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        """Lista todos os checkpoints disponíveis na thread, resolvendo seus blobs."""
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            return
        
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        
        query = self.collection.document(thread_id).collection("checkpoints")
        
        if before and "configurable" in before and "checkpoint_id" in before["configurable"]:
            before_doc = query.document(before["configurable"]["checkpoint_id"]).get()
            if before_doc.exists:
                before_time = before_doc.to_dict().get("created_at")
                query = query.where(filter=firestore.FieldFilter("created_at", "<", before_time))
        
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
        
        if limit:
            query = query.limit(limit)
        
        docs = query.get()
        
        for doc in docs:
            data = doc.to_dict()
            checkpoint = pickle.loads(data["checkpoint"])
            
            metadata_raw = data.get("metadata")
            if isinstance(metadata_raw, bytes):
                metadata = pickle.loads(metadata_raw)
            else:
                metadata = metadata_raw or {}
                
            parent_id = data.get("parent_id")
            
            # Carrega blobs para esse checkpoint
            versions = checkpoint.get("channel_versions", {})
            channel_values = {}
            if versions:
                blobs_ref = self.collection.document(thread_id).collection("blobs")
                doc_refs = [blobs_ref.document(f"{checkpoint_ns}::{k}::{v}") for k, v in versions.items()]
                blob_docs = self.db.get_all(doc_refs)
                for blob_doc in blob_docs:
                    if blob_doc.exists:
                        blob_data = blob_doc.to_dict()
                        type_str = blob_data.get("type")
                        bytes_data = blob_data.get("data")
                        parts = blob_doc.id.split("::")
                        if len(parts) >= 2:
                            channel_name = parts[-2]
                            if type_str != "empty":
                                channel_values[channel_name] = self.serde.loads_typed((type_str, bytes_data))
            
            checkpoint["channel_values"] = channel_values
            
            # Carrega writes
            writes = []
            writes_docs = self.collection.document(thread_id).collection("writes").where(filter=firestore.FieldFilter("checkpoint_id", "==", doc.id)).get()
            for w_doc in writes_docs:
                w_data = w_doc.to_dict()
                w_type = w_data.get("type", "pickle")
                w_raw = w_data.get("value")
                if w_type == "pickle":
                    w_val = pickle.loads(w_raw)
                else:
                    w_val = self.serde.loads_typed((w_type, w_raw))
                writes.append((w_data.get("task_id"), w_data.get("channel"), w_val))
                
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": doc.id}},
                checkpoint=checkpoint,
                metadata=metadata,
                pending_writes=writes,
                parent_config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": parent_id}} if parent_id else None
            )

    # --- IMPLEMENTAÇÃO DE MÉTODOS ASSÍNCRONOS (Obrigatórios para concorrência) ---

    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Versão assíncrona de get_tuple."""
        return self.get_tuple(config)

    async def aput(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: dict) -> Dict[str, Any]:
        """Versão assíncrona de put."""
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: Dict[str, Any], writes: Sequence[Tuple[str, Any]], task_id: str) -> None:
        """Versão assíncrona de put_writes."""
        return self.put_writes(config, writes, task_id)
        
    async def alist(self, config: Optional[Dict[str, Any]], *, filter: Optional[Dict[str, Any]] = None, before: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> Iterator[CheckpointTuple]:
        """Versão assíncrona de list."""
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item
