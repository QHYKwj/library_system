from db import settings

def get_algolia():
    """
    返回 Algolia index；未配置或 SDK 不匹配则返回 None。
    """
    if not getattr(settings, "ALGOLIA_APP_ID", None) or not getattr(settings, "ALGOLIA_ADMIN_KEY", None):
        return None
    if not getattr(settings, "ALGOLIA_INDEX", None):
        return None

    try:
        from algoliasearch.search.client import SearchClient

        # ✅ 兼容：新 SDK 有 SearchClient.create；老 SDK 可能直接构造
        if hasattr(SearchClient, "create"):
            client = SearchClient.create(settings.ALGOLIA_APP_ID, settings.ALGOLIA_ADMIN_KEY)
        else:
            client = SearchClient(settings.ALGOLIA_APP_ID, settings.ALGOLIA_ADMIN_KEY)

        # ✅ 兼容：init_index / initIndex
        if hasattr(client, "init_index"):
            return client.init_index(settings.ALGOLIA_INDEX)
        if hasattr(client, "initIndex"):
            return client.initIndex(settings.ALGOLIA_INDEX)

        return None
    except Exception:
        # Algolia 初始化失败时，不影响主业务
        return None


def book_to_object(book, publisher_name: str | None):
    return {
        "objectID": str(book.book_id),
        "book_id": int(book.book_id),
        "title": book.title,
        "subtitle": book.subtitle,
        "isbn": book.isbn,
        "publisher_id": int(book.publisher_id) if getattr(book, "publisher_id", None) else None,
        "publisher_name": publisher_name,
        "category": book.category,
        "language": book.language,
        "price": float(book.price) if book.price is not None else None,
        "summary": book.summary,
        "total_copies": int(book.total_copies),
        "available_copies": int(book.available_copies),
        "is_available": bool(book.available_copies and book.available_copies > 0),
    }


def upsert_book(book, publisher_name: str | None):
    idx = get_algolia()
    if not idx:
        return

    obj = book_to_object(book, publisher_name)

    # ✅ 兼容：save_object / saveObject / save_objects / saveObjects
    if hasattr(idx, "save_object"):
        idx.save_object(obj)
    elif hasattr(idx, "saveObject"):
        idx.saveObject(obj)
    elif hasattr(idx, "save_objects"):
        idx.save_objects([obj])
    elif hasattr(idx, "saveObjects"):
        idx.saveObjects([obj])


def delete_book(book_id: int):
    idx = get_algolia()
    if not idx:
        return

    # ✅ 兼容：delete_object / deleteObject
    if hasattr(idx, "delete_object"):
        idx.delete_object(str(book_id))
    elif hasattr(idx, "deleteObject"):
        idx.deleteObject(str(book_id))
