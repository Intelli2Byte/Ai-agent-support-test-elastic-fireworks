from elasticsearch import Elasticsearch

from config import ELASTICSEARCH_API_KEY, ELASTICSEARCH_URL

_client = None


def get_client() -> Elasticsearch:
    global _client
    if _client is None:
        _client = Elasticsearch(
            ELASTICSEARCH_URL,
            api_key=ELASTICSEARCH_API_KEY,
            request_timeout=30,
        )
    return _client
