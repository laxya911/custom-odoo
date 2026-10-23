# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    meta_title = fields.Char(
        string="Meta Title",
        translate=True,
        help="Optional SEO title for the product page."
    )
    meta_description = fields.Text(
        string="Meta Description",
        translate=True,
        help="Optional SEO meta description for the product page."
    )
