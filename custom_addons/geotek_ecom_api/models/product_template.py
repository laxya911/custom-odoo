# -*- coding: utf-8 -*-

from odoo import models, api, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def get_ecom_product_details(self, product_id):
        template = self.browse(int(product_id))
        if not template.exists() or not template.is_published:
            return None
        
        # Build optimized dictionary without base64 images
        res = {
            'template': {
                'id': template.id,
                'name': template.name,
                'list_price': template.list_price,
                'description_sale': template.description_sale or '',
                'website_description': template.website_description or '',
                'description_ecommerce': getattr(template, 'description_ecommerce', ''),
                'categ_id': [template.categ_id.id, template.categ_id.name] if template.categ_id else False,
                'public_categ_ids': template.public_categ_ids.ids,
                'public_category_names': template.public_categ_ids.mapped('name'),
                'product_tag_ids': template.product_tag_ids.ids,
                'product_tag_names': template.product_tag_ids.mapped('name'),
                'is_published': template.is_published,
                'default_code': template.default_code,
                'country_of_origin': template.country_of_origin.code if getattr(template, 'country_of_origin', None) else False,
                'hs_code': getattr(template, 'hs_code', False),
                'l10n_in_hsn_code': getattr(template, 'l10n_in_hsn_code', False),
                'product_template_image_ids': template.product_template_image_ids.ids,
            },
            'attributeLines': [],
            'variants': [],
            'alternativeProducts': template.alternative_product_ids.ids,
            'accessoryProducts': template.accessory_product_ids.ids,
            'optionalProducts': template.optional_product_ids.ids,
        }

        # Fetch Attribute Lines
        for line in template.attribute_line_ids:
            values = []
            for val in line.product_template_value_ids:
                values.append({
                    'id': val.id,
                    'name': val.name,
                    'price_extra': val.price_extra,
                    'html_color': val.html_color,
                    'product_attribute_value_id': [val.product_attribute_value_id.id, val.product_attribute_value_id.name]
                })
            res['attributeLines'].append({
                'id': line.id,
                'attribute_id': [line.attribute_id.id, line.attribute_id.name],
                'values': values
            })

        # Fetch Variants
        for variant in template.product_variant_ids:
            res['variants'].append({
                'id': variant.id,
                'name': variant.name,
                'display_name': variant.display_name,
                'default_code': variant.default_code,
                'lst_price': variant.lst_price,
                'price_extra': getattr(variant, 'price_extra', 0.0),
                'product_template_attribute_value_ids': variant.product_template_attribute_value_ids.ids,
            })

        return res
