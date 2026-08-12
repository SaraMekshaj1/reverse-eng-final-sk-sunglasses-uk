"""
ADAPT THIS FILE for every new project -- this is where raw API JSON gets
mapped onto the Item dataclass. Expect to rewrite this file from scratch
each time; the shape is never the same twice.

Unlike the old ProductParser, this raises ParseError on a bad hit instead
of swallowing it and returning None -- FetchService catches that and
routes the raw record to the failed-item store so nothing silently
disappears.
"""
from __future__ import annotations

from typing import Any, Optional

from app.abstraction.base_hit_parser import BaseHitParser
from app.exceptions.scraper_exceptions import ParseError
from app.models.item import Item

# The price list that actually carries live offer/discount data for the GB
# storefront. LISTPRICE always mirrors offerPrice == listPrice with zero
# discount, so it's useless for sale tracking.
PRICE_LIST_KEY = "DefaultOfferPriceList_GB"
BASE_URL = "https://www.sunglasshut.com"


class ItemParser(BaseHitParser):
    def parse(self, raw_record: dict[str, Any]) -> Item:
        try:
            attrs = raw_record.get("attributes", {})
            attrs_translated = raw_record.get("attributes_translated", {})
            categories = raw_record.get("categories", []) or []
            prices_block = raw_record.get("prices", {}).get(PRICE_LIST_KEY, {})

            list_price = prices_block.get("listPrice")
            offer_price = prices_block.get("offerPrice")

            object_id = raw_record.get("objectID", "")
            product_id = raw_record.get("productId", "")
            if not object_id or not product_id:
                raise ParseError("Hit missing objectID/productId")

            return Item(
                object_id=object_id,
                product_id=product_id,
                sku=attrs.get("SKU") or attrs.get("DISPLAYSKU"),
                brand=attrs.get("BRAND"),
                model=attrs.get("MODEL_NAME") or attrs_translated.get("MODEL_NAME"),
                gender=attrs.get("GENDER"),
                frame_shape=attrs.get("FRAME_SHAPE"),
                frame_material=attrs_translated.get("FRAME_MATERIAL_FACET"),
                lens_color=attrs_translated.get("LENS_COLOR_FACET"),
                front_color=attrs_translated.get("FRONT_COLOR"),
                product_type=attrs.get("PRODUCT_TYPE"),
                price=offer_price,
                list_price=list_price,
                currency=prices_block.get("currency"),
                discount_percentage=prices_block.get("percentageDiscount"),
                discount_amount=prices_block.get("amountOfDiscount"),
                on_sale=bool(
                    list_price is not None
                    and offer_price is not None
                    and offer_price < list_price
                ),
                inventory=raw_record.get("inventoryQuantity"),
                is_best_seller="Best_Seller" in categories,
                is_polarized=attrs.get("POLARIZED", "FALSE").upper() == "TRUE",
                is_customizable=attrs.get("CUSTOMIZABLE", "FALSE").upper() == "TRUE",
                image_url=self._first_image_url(raw_record.get("attachments", [])),
                url=BASE_URL + raw_record.get("url", ""),
            )
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError(f"Failed to parse hit: {exc}") from exc

    @staticmethod
    def _first_image_url(attachments: list) -> Optional[str]:
        """Prefer the PLP (product-listing-page) front image; fall back to any image."""
        for a in attachments:
            if a.get("rule") == "PLP" and a.get("name") == "Front":
                return a.get("url")
        return attachments[0].get("url") if attachments else None
