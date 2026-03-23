from pydantic import BaseModel


class Dimensions(BaseModel):
    width: float
    height: float
    depth: float


class Review(BaseModel):
    rating: int
    comment: str
    date: str
    reviewerName: str
    reviewerEmail: str


class Meta(BaseModel):
    createdAt: str
    updatedAt: str
    barcode: str
    qrCode: str


class Product(BaseModel):
    id: int
    title: str
    description: str
    category: str
    price: float
    discountPercentage: float
    rating: float
    stock: int
    tags: list[str]
    brand: str | None = None
    sku: str
    weight: float
    dimensions: Dimensions
    warrantyInformation: str
    shippingInformation: str
    availabilityStatus: str
    reviews: list[Review]
    returnPolicy: str
    minimumOrderQuantity: int
    meta: Meta
    thumbnail: str
    images: list[str]


class ProductList(BaseModel):
    products: list[Product]
    total: int
    skip: int
    limit: int


class ProductCategory(BaseModel):
    slug: str
    name: str
    url: str
