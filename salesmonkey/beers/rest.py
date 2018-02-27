from webargs import fields
from werkzeug.exceptions import NotFound, BadRequest
from webargs.flaskparser import use_args

from flask_apispec import (
    FlaskApiSpec,
    marshal_with,
    MethodResource,
    use_kwargs
)

from ..erpnext_client.schemas import (
    ERPItemSchema,
)

from ..erpnext_client.documents import (
    ERPItem
)

from ..erpnext import erp_client
from ..rest import api_v1


@marshal_with(ERPItemSchema(many=True))
class BeerList(MethodResource):
    """
    Return a list of beers
    """
    @use_kwargs({'item_group': fields.Str()})
    def get(self, **kwargs):
        item_group = kwargs.get('item_group', "Bières du Singe")

        items = erp_client.query(ERPItem).list(erp_fields=["name", "description", "disabled", "item_code", "web_long_description", "thumbnail"],
                                               filters=[["Item", "show_in_website", "=", "1"],
                                                        ["Item", "is_sales_item", "=", True],
                                                        ["Website Item Group", "item_group", "=", item_group]])

        return items

api_v1.register('/beers/', BeerList)

@marshal_with(ERPItemSchema())
class BeerDetails(MethodResource):
    """
    Return details of a beer
    """
    @use_kwargs({'slug': fields.Str()})
    def get(self, **kwargs):
        beer_slug = kwargs.get('slug', None)

        if beer_slug is None:
            raise NotFound

        item = erp_client.query(ERPItem).get(beer_slug,
                                             fields=["name", "description", "disabled", "item_code", "web_long_description", "website_specifications", "thumbnail"],
                                             filters=[["Item", "show_in_website", "=", "1"],
                                                      ["Item", "is_sales_item", "=", True]])


        return item

api_v1.register('/beers/<slug>', BeerDetails)
