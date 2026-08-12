"""
ADAPT THIS FILE for every new project -- this instance models one product
hit from the Sunglass Hut Algolia index.

Keep `is_valid()` and `dedup_key()` -- the rest of the pipeline
(deduplication_service, export_service) relies on both existing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass(slots=True)
class Item:
    object_id: str
    product_id: str
    sku: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    gender: Optional[str] = None
    frame_shape: Optional[str] = None
    frame_material: Optional[str] = None
    lens_color: Optional[str] = None
    front_color: Optional[str] = None
    product_type: Optional[str] = None

    # --- pricing & promotions -----------------------------------------
    price: Optional[float] = None          # offerPrice (current selling price)
    list_price: Optional[float] = None     # listPrice (undiscounted price)
    currency: Optional[str] = None
    discount_percentage: Optional[float] = None
    discount_amount: Optional[float] = None
    on_sale: bool = False                  # True if offerPrice < listPrice

    # --- stock & merchandising signal ----------------------------------
    inventory: Optional[int] = None
    is_best_seller: bool = False
    is_polarized: bool = False
    is_customizable: bool = False

    # --- media & links --------------------------------------------------
    image_url: Optional[str] = None
    url: str = ""

    def is_valid(self) -> bool:
        """Minimal sanity check before an Item is allowed to be exported."""
        return bool(self.object_id) and bool(self.product_id)

    def dedup_key(self) -> str:
        """Algolia's objectID uniquely identifies each record in the index."""
        return self.object_id

    def to_row(self) -> dict[str, Any]:
        """Flat dict used by CSV/row-based exporters."""
        return asdict(self)
