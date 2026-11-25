# -*- coding: utf-8 -*-
# Copyright (c) 2026, Grintsys and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.password import get_decrypted_password, set_encrypted_password

from posawesome.posawesome.api import posapp

KEY = "1234"


class TestPosAppSecurity(FrappeTestCase):
    """Phase 1 hardening: server-side supervisor key, SQL parameters and endpoint guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        names = frappe.get_all("POS Profile", pluck="name", limit=1)
        cls.profile = names[0] if names else None

    def setUp(self):
        if not self.profile:
            self.skipTest("No POS Profile available in this site")
        frappe.set_user("Administrator")
        set_encrypted_password("POS Profile", self.profile, KEY, "password_manager")
        frappe.db.set_value(
            "POS Profile", self.profile, "password_manager", "*****", update_modified=False
        )
        self._clear_attempts()

    def tearDown(self):
        frappe.set_user("Administrator")
        if self.profile:
            self._clear_attempts()
            frappe.db.rollback()

    def _clear_attempts(self):
        for user in ("Administrator", "Guest"):
            frappe.cache().delete_value(
                "posa_auth_failures:{0}:{1}".format(user, self.profile)
            )

    def _history_count(self, auth_type):
        return frappe.db.count(
            "Historial de autorizaciones en POS",
            {"type": auth_type, "pos_profile": self.profile},
        )

    # ---- supervisor key -------------------------------------------------

    def test_correct_key_authorizes_and_logs_history(self):
        before = self._history_count("Descuento Factura")
        res = posapp.verify_authorization(self.profile, KEY, "Descuento Factura", 25)
        self.assertTrue(res["authorized"])
        self.assertEqual(self._history_count("Descuento Factura"), before + 1)
        row = frappe.get_doc("Historial de autorizaciones en POS", res["history"])
        self.assertEqual(row.user, "Administrator")
        self.assertEqual(row.docstatus, 1)
        self.assertEqual(float(row.amount), 25.0)

    def test_wrong_key_is_rejected_and_not_logged(self):
        before = self._history_count("Cancelar Factura")
        res = posapp.verify_authorization(self.profile, "9999", "Cancelar Factura", 10)
        self.assertFalse(res["authorized"])
        self.assertEqual(res["reason"], "invalid")
        self.assertEqual(self._history_count("Cancelar Factura"), before)

    def test_lockout_after_too_many_failures(self):
        for _ in range(posapp.AUTH_MAX_ATTEMPTS):
            res = posapp.verify_authorization(self.profile, "0000", "Eliminar Producto", 1)
            self.assertEqual(res["reason"], "invalid")
        before = self._history_count("Eliminar Producto")
        # Even the correct key is refused while the lock is active
        res = posapp.verify_authorization(self.profile, KEY, "Eliminar Producto", 1)
        self.assertFalse(res["authorized"])
        self.assertTrue(res.get("locked"))
        self.assertEqual(res["reason"], "locked")
        self.assertEqual(self._history_count("Eliminar Producto"), before)

    def test_successful_attempt_resets_failure_counter(self):
        for _ in range(posapp.AUTH_MAX_ATTEMPTS - 1):
            posapp.verify_authorization(self.profile, "0000", "Descuento Producto", 0)
        self.assertTrue(
            posapp.verify_authorization(self.profile, KEY, "Descuento Producto", 0)["authorized"]
        )
        for _ in range(posapp.AUTH_MAX_ATTEMPTS - 1):
            res = posapp.verify_authorization(self.profile, "0000", "Descuento Producto", 0)
            self.assertEqual(res["reason"], "invalid")

    def test_invalid_type_and_guest_are_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            posapp.verify_authorization(self.profile, KEY, "Tipo Inventado", 0)
        frappe.set_user("Guest")
        with self.assertRaises(frappe.PermissionError):
            posapp.verify_authorization(self.profile, KEY, "Descuento Factura", 0)

    def test_profile_without_key_cannot_authorize(self):
        frappe.db.sql(
            """DELETE FROM `__Auth`
            WHERE doctype='POS Profile' AND name=%s AND fieldname='password_manager'""",
            self.profile,
        )
        res = posapp.verify_authorization(self.profile, "", "Descuento Factura", 0)
        self.assertFalse(res["authorized"])
        self.assertEqual(res["reason"], "not_configured")

    def test_key_is_never_sent_to_the_browser(self):
        doc = frappe.get_doc("POS Profile", self.profile)
        self.assertNotEqual(doc.password_manager, KEY)
        data = {}
        posapp.update_opening_shift_data(data, self.profile)
        self.assertFalse(data["pos_profile"].password_manager)
        self.assertNotIn(KEY, frappe.as_json(data["pos_profile"]))

    def test_migration_patch_encrypts_plain_text_key_and_is_idempotent(self):
        from erpnext.patches.v14_0 import encrypt_pos_profile_password_manager as patch_mod

        frappe.db.sql(
            """DELETE FROM `__Auth`
            WHERE doctype='POS Profile' AND name=%s AND fieldname='password_manager'""",
            self.profile,
        )
        frappe.db.set_value(
            "POS Profile", self.profile, "password_manager", "clave-vieja-9", update_modified=False
        )
        patch_mod.execute()
        self.assertEqual(
            get_decrypted_password("POS Profile", self.profile, "password_manager"), "clave-vieja-9"
        )
        self.assertEqual(
            frappe.db.get_value("POS Profile", self.profile, "password_manager"), "*****"
        )
        patch_mod.execute()  # second run must not touch the encrypted value
        self.assertEqual(
            get_decrypted_password("POS Profile", self.profile, "password_manager"), "clave-vieja-9"
        )
        res = posapp.verify_authorization(self.profile, "clave-vieja-9", "Descuento Factura", 0)
        self.assertTrue(res["authorized"])

    # ---- SQL ------------------------------------------------------------

    def test_customer_addresses_is_parameterized(self):
        self.assertEqual(posapp.get_customer_addresses("x' OR '1'='1"), [])

    def test_item_group_filter_is_escaped(self):
        payload = "a' OR '1'='1"
        cond = posapp._item_group_like_condition(payload)
        self.assertEqual(
            cond, " AND item_group like " + frappe.db.escape("%" + payload + "%")
        )
        self.assertNotIn("%a' OR", cond)

    # ---- endpoint guards ------------------------------------------------

    def test_delete_invoice_only_deletes_pos_drafts(self):
        cases = [
            frappe._dict(docstatus=1, posa_is_printed=0, posa_pos_opening_shift="SHIFT-1"),
            frappe._dict(docstatus=0, posa_is_printed=1, posa_pos_opening_shift="SHIFT-1"),
            frappe._dict(docstatus=0, posa_is_printed=0, posa_pos_opening_shift=None),
        ]
        for values in cases:
            with patch.object(posapp.frappe.db, "get_value", return_value=values), patch.object(
                posapp.frappe, "delete_doc"
            ) as delete_mock:
                with self.assertRaises(frappe.ValidationError):
                    posapp.delete_invoice("ACC-SINV-TEST")
                delete_mock.assert_not_called()

        with patch.object(posapp.frappe.db, "get_value", return_value=None):
            with self.assertRaises(frappe.DoesNotExistError):
                posapp.delete_invoice("ACC-SINV-NOEXISTE")

        ok = frappe._dict(docstatus=0, posa_is_printed=0, posa_pos_opening_shift="SHIFT-1")
        with patch.object(posapp.frappe.db, "get_value", return_value=ok), patch.object(
            posapp.frappe, "delete_doc"
        ) as delete_mock:
            posapp.delete_invoice("ACC-SINV-TEST")
            delete_mock.assert_called_once()

    def test_delete_sales_invoice_rejects_submitted(self):
        with patch.object(posapp.frappe.db, "get_value", return_value=1), patch.object(
            posapp.frappe, "delete_doc"
        ) as delete_mock:
            with self.assertRaises(frappe.ValidationError):
                posapp.delete_sales_invoice("ACC-SINV-TEST")
            delete_mock.assert_not_called()

    def test_set_customer_info_rejects_unknown_fields(self):
        with self.assertRaises(frappe.ValidationError):
            posapp.set_customer_info("Cualquiera", "credit_limit", "1")

    def test_cash_movement_validation(self):
        open_shift = frappe._dict(status="Open", docstatus=1)
        closed_shift = frappe._dict(status="Closed", docstatus=1)

        with patch.object(posapp.frappe.db, "get_value", return_value=open_shift):
            self.assertEqual(posapp._validate_cash_movement("150.50", "S1", "Retiro"), 150.5)
            for bad_amount in (0, -5, "abc", None):
                with self.assertRaises(frappe.ValidationError):
                    posapp._validate_cash_movement(bad_amount, "S1", "Retiro")
            with self.assertRaises(frappe.ValidationError):
                posapp._validate_cash_movement(10, "S1", "Otro")

        with patch.object(posapp.frappe.db, "get_value", return_value=closed_shift):
            with self.assertRaises(frappe.ValidationError):
                posapp._validate_cash_movement(10, "S1", "Ingreso")
        with patch.object(posapp.frappe.db, "get_value", return_value=None):
            with self.assertRaises(frappe.ValidationError):
                posapp._validate_cash_movement(10, "S1", "Ingreso")
