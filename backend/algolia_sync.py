from db import settings
from algoliasearch.search.client import SearchClient

def get_algolia():
    if not settings.ALGOLIA_APP_ID or not settings.ALGOLIA_ADMIN_KEY:
        return None
    client = SearchClient.create(settings.ALGOLIA_APP_ID, settings.ALGOLIA_ADMIN_KEY)
    index = client.init_index(settings.ALGOLIA_INDEX)
    return index

def book_to_object(book, publisher_name: str | None):
    return {
        "objectID": str(book.book_id),
        "book_id": book.book_id,
        "title": book.title,
        "subtitle": book.subtitle,
        "isbn": book.isbn,
        "publisher_name": publisher_name,
        "category": book.category,
        "language": book.language,
        "price": float(book.price) if book.price is not None else None,
        "summary": book.summary,
        "total_copies": book.total_copies,
        "available_copies": book.available_copies,
    }

def upsert_book(book, publisher_name: str | None):
    idx = get_algolia()
    if not idx:
        return
    idx.save_object(book_to_object(book, publisher_name))

def delete_book(book_id: int):
    idx = get_algolia()
    if not idx:
        return
    idx.delete_object(str(book_id))
