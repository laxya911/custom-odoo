# -*- coding: utf-8 -*-
{
    'name': 'Product SEO Fields',
    'version': '19.0.1.0.0',
    'summary': 'Add Meta Title and Meta Description to Product Templates for Next.js SEO',
    'description': """
        This module adds two optional fields to product.template:
        - meta_title: Optional SEO title for the product page.
        - meta_description: Optional SEO meta description for the product page.
        
        These fields are translatable and intended for consumption by external storefront APIs.
        Dependency is minimal (only 'product') to avoid unnecessary overhead from 'stock' or 'website_sale'.
    """,
    'author': 'Geotek',
    'category': 'Product',
    'depends': ['product'],
    'data': [
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
