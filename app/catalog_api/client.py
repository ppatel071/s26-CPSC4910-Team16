from urllib.parse import quote
import requests
from app.catalog_api.models import Product, ProductCategory, ProductList

# 194 Products
# Use limit=0 to fetch all
# https://dummyjson.com/docs/


class DummyJSONClient:
    BASE_URL = "https://dummyjson.com"

    def __init__(self, timeout: int = 5):
        self.session = requests.Session()
        self.timeout = timeout

    def _summarize_result(self, data):
        if isinstance(data, dict):
            summary = {}
            for key in ("total", "skip", "limit", "id", "title", "name", "slug"):
                if key in data:
                    summary[key] = data[key]
            if "products" in data and isinstance(data["products"], list):
                summary["product_count"] = len(data["products"])
            return summary
        if isinstance(data, list):
            return {"result_count": len(data)}
        return {"result_type": type(data).__name__}

    def _get(self, path: str, params: dict | None = None):
        url = f"{self.BASE_URL}{path}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception:
            raise

    def get_products(self, limit: int = 30, skip: int = 0) -> ProductList:
        data = self._get("/products", {"limit": limit, "skip": skip})
        return ProductList(**data)

    def get_all_products(self) -> ProductList:
        data = self._get("/products", {"limit": 0})
        return ProductList(**data)

    def get_product(self, product_id: int) -> Product:
        data = self._get(f"/products/{product_id}")
        return Product(**data)

    def search_products(
        self, query: str, limit: int = 30, skip: int = 0
    ) -> ProductList:
        data = self._get(
            "/products/search", {"q": query, "limit": limit, "skip": skip}
        )
        return ProductList(**data)

    def get_by_category(
        self, category: str, limit: int = 30, skip: int = 0
    ) -> ProductList:
        encoded_category = quote(category, safe="")
        data = self._get(
            f"/products/category/{encoded_category}", {"limit": limit, "skip": skip}
        )
        return ProductList(**data)

    def get_categories(self) -> list[ProductCategory]:
        data = self._get("/products/categories")
        return [
            category if isinstance(category, ProductCategory) else ProductCategory(**category)
            for category in data
        ]


catalog_client = DummyJSONClient()
