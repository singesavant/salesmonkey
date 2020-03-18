from flask_login import login_required

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource,
    use_kwargs
)

from webargs import fields
from webargs.flaskparser import use_args


from ..rest import api_v1

from ..erpnext import erp_client

from erpnext_client.schemas import (
    ERPItemSchema
)

from erpnext_client.documents import (
    ERPItem,
)

@marshal_with(ERPItemSchema(many=True))
class ItemList(MethodResource):
    @use_kwargs({'item_group': fields.Str()})
    def get(self, **kwargs):
        item_group = kwargs.get('item_group', "")

        items_no_variant = erp_client.query(ERPItem).list(erp_fields=["name", "description", "item_code", "total_projected_qty", "web_long_description", "standard_rate", "thumbnail"],
                                                          filters=[["Item", "show_in_website", "=", "1"],
                                                                   ["Item", "has_variants", "=", "0"],
                                                                   ["Website Item Group", "item_group", "=", item_group]])

        # Items with variants
        items_variants = erp_client.query(ERPItem).list(erp_fields=["name", "description", "item_code", "total_projected_qty", "web_long_description", "standard_rate", "thumbnail"],
                                                        filters=[["Item", "show_variant_in_website", "=", "1"],
                                                                 ["Website Item Group", "item_group", "=", item_group]])


        items = items_no_variant + items_variants

        return items

api_v1.register('/brewshop/items/', ItemList)
