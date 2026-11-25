# -*- coding: utf-8 -*-
# Copyright (c) 2026, Grintsys and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.password import (
    get_decrypted_password,
    set_encrypted_password,
    update_password,
)

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
        for user in (
            "Administrator",
            "Guest",
            "test_pos_supervisor@example.com",
            "test_pos_cashier@example.com",
        ):
            frappe.cache().delete_value(
                "posa_auth_failures:{0}:{1}".format(user, self.profile)
            )
            frappe.cache().delete_value(
                "posa_auth_sup_failures:{0}:{1}".format(user, self.profile)
            )

    def _ensure_test_user(self, email, username, password, roles):
        posapp.ensure_supervisor_role()
        if not frappe.db.exists("User", email):
            user = frappe.get_doc(
                {
                    "doctype": "User",
                    "email": email,
                    "first_name": username,
                    "username": username,
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
            )
            user.insert(ignore_permissions=True)
        else:
            user = frappe.get_doc("User", email)
            user.username = username
            user.enabled = 1
            user.save(ignore_permissions=True)

        user.roles = []
        for r in roles:
            user.append("roles", {"role": r})
        user.save(ignore_permissions=True)
        update_password(email, password)
        return email

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

    # ---- Phase 2: Supervisor POS Profile user+password, reason & unexpected close ----

    def test_supervisor_role_and_user_password_authorization(self):
        sup_email = self._ensure_test_user(
            "test_pos_supervisor@example.com",
            "sup_pos_test",
            "SupSecret#2026",
            ["Sales User", posapp.SUPERVISOR_ROLE],
        )
        cashier_email = self._ensure_test_user(
            "test_pos_cashier@example.com",
            "cajero_pos_test",
            "CashierSecret#2026",
            ["Sales User"],
        )
        self.assertTrue(frappe.db.exists("Role", posapp.SUPERVISOR_ROLE))

        frappe.set_user(cashier_email)
        # Authorize using supervisor username + password
        res = posapp.verify_authorization(
            self.profile,
            code="SupSecret#2026",
            type="Descuento Factura",
            amount=50,
            supervisor_user="sup_pos_test",
        )
        self.assertTrue(res["authorized"])
        self.assertEqual(res["authorized_by"], sup_email)
        row = frappe.get_doc("Historial de autorizaciones en POS", res["history"])
        self.assertEqual(row.user, cashier_email)
        self.assertEqual(row.authorized_by, sup_email)

        # Wrong supervisor password fails
        bad = posapp.verify_authorization(
            self.profile,
            code="ClaveErronea",
            type="Descuento Factura",
            amount=50,
            supervisor_user=sup_email,
        )
        self.assertFalse(bad["authorized"])
        self.assertEqual(bad["reason"], "invalid")

    def test_administrator_and_non_supervisor_are_rejected(self):
        cashier_email = self._ensure_test_user(
            "test_pos_cashier@example.com",
            "cajero_pos_test",
            "CashierSecret#2026",
            ["Sales User"],
        )
        frappe.set_user(cashier_email)

        # Decision 4: Administrator cannot be used as authorizing supervisor
        admin_res = posapp.verify_authorization(
            self.profile,
            code="any",
            type="Descuento Producto",
            amount=0,
            supervisor_user="Administrator",
        )
        self.assertFalse(admin_res["authorized"])
        self.assertEqual(admin_res["reason"], "invalid_supervisor")

        # Decision 1: A user without "Supervisor POS Profile" role cannot authorize
        non_sup = posapp.verify_authorization(
            self.profile,
            code="CashierSecret#2026",
            type="Descuento Producto",
            amount=0,
            supervisor_user=cashier_email,
        )
        self.assertFalse(non_sup["authorized"])
        self.assertEqual(non_sup["reason"], "not_supervisor")

    def test_self_supervisor_auto_authorizes_and_requires_reason_on_cancel_or_delete(self):
        sup_email = self._ensure_test_user(
            "test_pos_supervisor@example.com",
            "sup_pos_test",
            "SupSecret#2026",
            ["Sales User", posapp.SUPERVISOR_ROLE],
        )
        frappe.set_user(sup_email)
        data = {}
        posapp.update_opening_shift_data(data, self.profile)
        self.assertTrue(data["is_pos_supervisor"])

        # Discount does not require password or reason when logged in as supervisor
        disc_res = posapp.verify_authorization(
            self.profile, code="", type="Descuento Producto", amount=0
        )
        self.assertTrue(disc_res["authorized"])
        self.assertEqual(disc_res["authorized_by"], sup_email)

        # Cancel Invoice and Delete Item require a non-empty reason (Decision 3)
        no_reason = posapp.verify_authorization(
            self.profile, code="", type="Cancelar Factura", amount=120, reason="   "
        )
        self.assertFalse(no_reason["authorized"])
        self.assertEqual(no_reason["reason"], "missing_reason")

        with_reason = posapp.verify_authorization(
            self.profile,
            code="",
            type="Cancelar Factura",
            amount=120,
            reason="Cliente solicitó cambio de método de pago",
        )
        self.assertTrue(with_reason["authorized"])
        row = frappe.get_doc("Historial de autorizaciones en POS", with_reason["history"])
        self.assertEqual(row.user, sup_email)
        self.assertEqual(row.authorized_by, sup_email)
        self.assertEqual(row.reason, "Cliente solicitó cambio de método de pago")

    def test_register_unexpected_close_is_idempotent_by_client_session_id(self):
        session_uuid = "sess-test-" + frappe.generate_hash(length=10)
        first = posapp.register_unexpected_close(
            client_session_id=session_uuid,
            pos_profile=self.profile,
            pending_total=1250.0,
            currency="HNL",
            items_count=3,
            reason="render-process-gone",
            machine_name="CAJA-01-PC",
            app_version="1.1.0",
        )
        self.assertTrue(first["ok"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(first["voucher"].startswith("HIS-POS-"))

        second = posapp.register_unexpected_close(
            client_session_id=session_uuid,
            pos_profile=self.profile,
            pending_total=1250.0,
            currency="HNL",
            items_count=3,
            reason="render-process-gone",
            machine_name="CAJA-01-PC",
            app_version="1.1.0",
        )
        self.assertTrue(second["ok"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(second["voucher"], first["voucher"])
