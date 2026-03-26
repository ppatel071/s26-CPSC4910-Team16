from typing import List

from app.catalog_api.client import catalog_client
from app.catalog_api.models import Product, ProductCategory, ProductList
from app.models import SponsorCatalogItem


CATALOG_PAGE_SIZE = 30


def get_organization_catalog_items(
    organization_id: int,
) -> List[SponsorCatalogItem]:
    return (
        SponsorCatalogItem.query.filter_by(organization_id=organization_id)
        .order_by(SponsorCatalogItem.product_name.asc(), SponsorCatalogItem.catalog_id.asc())
        .all()
    )


def get_products_by_external_id() -> dict[int, Product]:
    products = catalog_client.get_all_products().products
    return {product.id: product for product in products}


def get_catalog_products_for_items(
    catalog_items: List[SponsorCatalogItem],
) -> List[tuple[SponsorCatalogItem, Product | None]]:
    products_by_id = get_products_by_external_id()
    return [(item, products_by_id.get(item.external_id)) for item in catalog_items]


def get_catalog_products_for_organization(
    organization_id: int,
) -> List[tuple[SponsorCatalogItem, Product | None]]:
    return get_catalog_products_for_items(get_organization_catalog_items(organization_id))


def browse_catalog_products(
    *,
    query: str = "",
    category: str = "",
    page: int = 1,
    page_size: int = CATALOG_PAGE_SIZE,
) -> ProductList:
    safe_page = max(page, 1)
    skip = (safe_page - 1) * page_size
    clean_query = (query or "").strip()
    clean_category = (category or "").strip()

    if clean_query:
        return catalog_client.search_products(clean_query, limit=page_size, skip=skip)
    if clean_category:
        return catalog_client.get_by_category(clean_category, limit=page_size, skip=skip)
    return catalog_client.get_products(limit=page_size, skip=skip)


def get_catalog_categories() -> List[ProductCategory]:
    return sorted(catalog_client.get_categories(), key=lambda category: category.name.lower())


def get_catalog_item_lookup(
    catalog_items: List[SponsorCatalogItem],
) -> tuple[set[int], dict[int, int]]:
    return (
        {item.external_id for item in catalog_items},
        {item.external_id: item.catalog_id for item in catalog_items},
    )
