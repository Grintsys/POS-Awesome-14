# Copyright (c) 2025, Youssef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class HistorialdeautorizacionesenPOS(Document):
	def validate(self):
		self.date_time = frappe.utils.now()
		self.user = frappe.session.user