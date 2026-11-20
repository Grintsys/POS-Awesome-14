# apps/posawesome/posawesome/api/search.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


@frappe.whitelist()
def quick_lookup(term: str):
    """
    Lookup exacto:
      1) Si term coincide EXACTO con un barcode → devuelve item_code (parent del barcode)
      2) Si term coincide EXACTO con Item.name o Item.item_code → devuelve item_code
    """
    term = (term or "").strip()
    if not term:
        return {}

    # 1) Barcode exacto
    item_from_barcode = frappe.db.get_value("Item Barcode", {"barcode": term}, "parent")
    if item_from_barcode:
        return {"item_code": item_from_barcode, "via": "barcode"}

    # 2) Item exacto (name o item_code)
    item_exact = (
        frappe.db.get_value("Item", {"name": term}, "name")
        or frappe.db.get_value("Item", {"item_code": term}, "name")
    )
    if item_exact:
        return {"item_code": item_exact, "via": "item_code"}

    return {}


@frappe.whitelist()
def items_prefix(term: str, limit: int = 20):
    """
    Búsqueda por PREFIJO (empieza con) sobre:
      - Item Barcode.barcode
      - Item.item_code
      - Item.item_name
      - Item.description

    Reglas:
      - Requiere al menos 3 caracteres
      - Devuelve hasta `limit` filas
      - Filtra items deshabilitados y no de venta
      - Ordena priorizando barcode-prefix > item_code-prefix > (name|desc)-prefix
    """
    term = (term or "").strip()
    if not term or len(term) < 3:
        return []

    like = f"{term}%"
    lim = cint(limit) or 20

    # NOTA: usamos SQL directo para poder rankear con CASE + EXISTS de forma portable y eficiente.
    # Los collations usuales de MariaDB/MySQL ya son case-insensitive para LIKE.
    # Sensibilidad a tildes depende del collation de la DB (si necesitas acento-insensitive total,
    # lo abordamos en una Fase 2 con columnas normalizadas e índices).
    sql = """
        SELECT
            i.name,
            i.item_code,
            i.item_name,
            i.description,
            -- ranking de prioridad:
            (CASE
               WHEN EXISTS (
                 SELECT 1 FROM `tabItem Barcode` b
                 WHERE b.parent = i.name AND b.barcode LIKE %(like)s
               ) THEN 1
               WHEN i.item_code LIKE %(like)s THEN 2
               WHEN i.item_name LIKE %(like)s OR i.description LIKE %(like)s THEN 3
               ELSE 9
             END) AS _rank
        FROM `tabItem` i
        WHERE i.disabled = 0
          AND i.is_sales_item = 1
          AND (
              i.item_code LIKE %(like)s
              OR i.item_name LIKE %(like)s
              OR i.description LIKE %(like)s
              OR EXISTS (
                  SELECT 1 FROM `tabItem Barcode` b
                  WHERE b.parent = i.name AND b.barcode LIKE %(like)s
              )
          )
        ORDER BY _rank ASC, i.item_code ASC
        LIMIT %(limit)s
    """

    rows = frappe.db.sql(sql, {"like": like, "limit": lim}, as_dict=True)
    # No devolvemos el campo interno de rank
    for r in rows:
        r.pop("_rank", None)
    return rows


@frappe.whitelist()
def items_contains(term: str, limit: int = 20):
    """
    Búsqueda CLÁSICA (contains) como fallback o cuando el usuario incluye '%':
      - Busca '%term%' en item_code, item_name, description y barcodes relacionados
      - Devuelve hasta `limit` filas
      - Filtra items deshabilitados y no de venta
      - Orden: item_code asc (puedes ajustar)
    """
    term = (term or "").strip()
    if not term:
        return []

    like = f"%{term}%"
    lim = cint(limit) or 20

    sql = """
        SELECT
            i.name,
            i.item_code,
            i.item_name,
            i.description
        FROM `tabItem` i
        WHERE i.disabled = 0
          AND i.is_sales_item = 1
          AND (
              i.item_code LIKE %(like)s
              OR i.item_name LIKE %(like)s
              OR i.description LIKE %(like)s
              OR EXISTS (
                  SELECT 1 FROM `tabItem Barcode` b
                  WHERE b.parent = i.name AND b.barcode LIKE %(like)s
              )
          )
        ORDER BY i.item_code ASC
        LIMIT %(limit)s
    """

    return frappe.db.sql(sql, {"like": like, "limit": lim}, as_dict=True)
