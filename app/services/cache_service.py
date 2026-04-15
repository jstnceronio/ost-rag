from app.embeddings.supabase_client import get_supabase_client
from app.embeddings.factory import create_embeddings

class CacheService:
    def __init__(self):
        self.supabase_client = get_supabase_client()
        self.embeddings = create_embeddings()

    def check_cache(self, query_embedding: list[float], threshold: float = 0.98) -> tuple[str, list[dict]] | None:
        response = self.supabase_client.rpc(
                "match_cache_queries",
                {
                    "p_query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": 1
                }
            ).execute()
        if not response.data:
            return None
        best_match = response.data[0]
        cache_id = best_match["id"]
        llm_response = best_match["llm_response"]
        source_metadata = best_match["source_metadata"]
        
        if self._validate_sources(source_metadata):
            return llm_response, source_metadata
        
        self._delete_expired_cache(cache_id)
        return None


    def save_to_cache(self, query_text: str, query_embedding: list[float], llm_response: str, sources: list):
        source_metadata_list = []
        added_doc_ids = set()
        
        for doc in sources:
                doc_id = doc.metadata.get("doc_id")
                version = doc.metadata.get("version")
                title = doc.metadata.get("title")
                url = doc.metadata.get("url")
                heading_path = doc.metadata.get("heading_path", [])
                chunk_id = doc.metadata.get("chunk_id")
                
                if doc_id and version is not None and doc_id not in added_doc_ids:
                    added_doc_ids.add(doc_id)
                    source_metadata_list.append({
                        "doc_id": doc_id, 
                        "version": version,
                        "title": title,
                        "url": url,
                        "heading_path": heading_path,
                        "chunk_id": chunk_id
                    })

        data_to_insert = {
            "query_text": query_text,
            "query_embedding": query_embedding,
            "llm_response": llm_response,
            "source_metadata": source_metadata_list
        }

        try:
            self.supabase_client.table("semantic_cache").insert(data_to_insert).execute()
        except Exception as e:
            print(f"Error saving to cache: {e}")


    def _validate_sources(self, cached_sources_metadata: list[dict]) -> bool:
        
        if not cached_sources_metadata:
            return True

        doc_ids = [source.get("doc_id") for source in cached_sources_metadata if source.get("doc_id")]
        
        if not doc_ids:
            return True

        from app.config import settings
        
        try:
            response = self.supabase_client.table(settings.supabase_table_name)\
                .select("metadata")\
                .in_("metadata->>doc_id", doc_ids)\
                .execute()
        except Exception as e:
            print(f"Error getting sources for validation: {e}")
            return False

        current_versions = {}
        for row in response.data:
            metadata = row.get("metadata", {})
            doc_id = metadata.get("doc_id")
            version = metadata.get("version")
            
            if doc_id and version is not None:
                current_versions[doc_id] = version

        for cached_source in cached_sources_metadata:
            cached_doc_id = cached_source.get("doc_id")
            cached_version = cached_source.get("version")
            
            if cached_doc_id not in current_versions:
                return False 
                
            if current_versions[cached_doc_id] != cached_version:
                return False 
                
        return True


    def _delete_expired_cache(self, cache_id: str):

        try:
            self.supabase_client.table("semantic_cache").delete().eq("id", cache_id).execute()
        except Exception as e:
            print(f"Error deleting expired cache entry: {e}")
