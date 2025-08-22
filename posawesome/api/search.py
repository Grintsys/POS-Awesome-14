# posawesome/posawesome/api/search.py
import frappe
from frappe.utils import cint
from frappe.query_builder import DocType, functions as fn

@frappe.whitelist()
def quick_lookup(term: str):
    """Match exacto: barcode o item_code ⇒ devolver item_code (para agregar directo)."""
    term = (term or "").strip()
    if not term:
        return {}

    # 1) Barcode exacto (Item Barcode.parent es el Item)
    item_from_barcode = frappe.db.get_value("Item Barcode", {"barcode": term}, "parent")
    if item_from_barcode:
        return {"item_code": item_from_barcode, "via": "barcode"}

    # 2) item_code / name exacto
    item_exact = (
        frappe.db.get_value("Item", {"name": term}, "name") or
        frappe.db.get_value("Item", {"item_code": term}, "name")
    )
    if item_exact:
        return {"item_code": item_exact, "via": "item_code"}

    return {}

@frappe.whitelist()
def items_prefix(term: str, limit: int = 20):
    """
    Búsqueda por PREFIJO (empieza con) en: barcode, item_code, item_name, description.
    Requiere al menos 3 caracteres. Devuelve lista ligera para el selector.
    """
    term = (term or "").strip()
    if not term or len(term) < 3:
        return []

    like = f"{term}%"   # solo prefijo

    Item = DocType("Item")
    Barcode = DocType("Item Barcode")

    q = (
        frappe.qb.from_(Item)
        .select(
            Item.name,
            Item.item_code,
            Item.item_name,
            Item.description,
        )
        .where((Item.disabled == 0) & (Item.is_sales_item == 1))
        .where(
            (Item.item_code.like(like)) |
            (Item.item_name.like(like)) |
            (Item.description.like(like)) |
            fn.Exists(
                frappe.qb.from_(Barcode)
                .select(Barcode.name)
                .where((Barcode.parent == Item.name) & (Barcode.barcode.like(like)))
            )
        )
        .orderby(Item.item_code)
        .limit(cint(limit))
    )

    return frappe.qb.run(q)
