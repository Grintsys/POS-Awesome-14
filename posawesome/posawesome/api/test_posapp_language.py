# -*- coding: utf-8 -*-
# Copyright (c) 2026, Grintsys and contributors
# For license information, please see license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import money_in_words

from posawesome.posawesome.api import posapp


class TestPosAppBackgroundLanguage(FrappeTestCase):
    def setUp(self):
        self._original_lang = getattr(frappe.local, "lang", None)

    def tearDown(self):
        frappe.local.lang = self._original_lang

    def test_submit_in_background_job_uses_explicit_spanish_lang_and_restores_worker_lang(self):
        frappe.local.lang = "en"
        captured = {}

        fake_invoice = MagicMock()
        fake_invoice.name = "SINV-TEST-LANG-001"
        fake_invoice.owner = "Administrator"

        def _fake_submit():
            captured["lang_during_submit"] = frappe.local.lang
            captured["in_words"] = money_in_words(300, "HNL")

        fake_invoice.submit.side_effect = _fake_submit

        with patch.object(posapp.frappe, "get_doc", return_value=fake_invoice), patch.object(
            posapp, "redeeming_customer_credit"
        ) as redeem_mock:
            posapp.submit_in_background_job(
                {
                    "invoice": fake_invoice.name,
                    "data": {},
                    "is_payment_entry": 0,
                    "total_cash": 0,
                    "cash_account": None,
                    "payments": [],
                    "lang": "es",
                }
            )

        self.assertEqual(captured["lang_during_submit"], "es")
        self.assertIn("Trescientos", captured["in_words"])
        self.assertNotIn("only.", captured["in_words"])
        self.assertEqual(frappe.local.lang, "en")
        redeem_mock.assert_called_once()

    def test_submit_in_background_job_falls_back_to_user_or_system_lang_without_explicit_lang(self):
        frappe.local.lang = "en"
        captured = {}

        fake_invoice = MagicMock()
        fake_invoice.name = "SINV-TEST-LANG-002"
        fake_invoice.owner = "cashier@example.com"

        def _fake_submit():
            captured["lang_during_submit"] = frappe.local.lang
            captured["in_words"] = money_in_words(1500, "HNL")

        fake_invoice.submit.side_effect = _fake_submit

        with patch.object(posapp.frappe, "get_doc", return_value=fake_invoice), patch.object(
            posapp, "get_user_lang", return_value="es"
        ) as get_lang_mock, patch.object(posapp, "redeeming_customer_credit"):
            posapp.submit_in_background_job(
                {
                    "invoice": fake_invoice.name,
                    "data": {},
                    "is_payment_entry": 0,
                    "total_cash": 0,
                    "cash_account": None,
                    "payments": [],
                }
            )

        get_lang_mock.assert_called_once_with("cashier@example.com")
        self.assertEqual(captured["lang_during_submit"], "es")
        self.assertIn("Quinientos", captured["in_words"])
        self.assertNotIn("only.", captured["in_words"])
        self.assertEqual(frappe.local.lang, "en")

    def test_submit_in_background_job_restores_worker_lang_on_error(self):
        frappe.local.lang = "en"

        fake_invoice = MagicMock()
        fake_invoice.name = "SINV-TEST-LANG-ERR"
        fake_invoice.owner = "Administrator"
        fake_invoice.submit.side_effect = RuntimeError("Simulated submit error")

        with patch.object(posapp.frappe, "get_doc", return_value=fake_invoice), patch.object(
            posapp, "redeeming_customer_credit"
        ):
            with self.assertRaises(RuntimeError):
                posapp.submit_in_background_job(
                    {
                        "invoice": fake_invoice.name,
                        "data": {},
                        "lang": "es",
                    }
                )

        self.assertEqual(frappe.local.lang, "en")
