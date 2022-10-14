from webargs import fields
from werkzeug.exceptions import NotFound, BadRequest
from webargs.flaskparser import use_args

from flask_apispec import FlaskApiSpec, marshal_with, MethodResource, use_kwargs

from erpnext_client.schemas import (
    ERPItemSchema,
)

from erpnext_client.documents import ERPItem, ERPWebsiteSlideshow

from ..erpnext import erp_client
from ..rest import api_v1

from salesmonkey import cache


@marshal_with(ERPItemSchema(many=True))
class BeerList(MethodResource):
    """
    Return a list of beers
    """

    @use_kwargs({"item_group": fields.Str()})
    @cache.memoize(timeout=60)
    def get(self, item_group=None):
        item_group = item_group or "Bières du Singe"

        items = erp_client.query(ERPItem).list(
            erp_fields=[
                "name",
                "description",
                "published",
                "item_code",
                "website_image",
                "thumbnail",
                "web_item_name",
            ],
            filters=[
                ["Website Item", "published", "=", "1"],
#                ["Item", "is_sales_item", "=", True],
                ["Website Item Group", "item_group", "=", item_group],
            ],
        )

        return items


api_v1.register("/beers/", BeerList)


class BeerItemSchema(ERPItemSchema):
    """
    Item Schema extended with a few calculations
    """

    slideshow_items = fields.Nested(
        "ERPWebsiteSlideshowItem", many=True, load_from="slideshow_items"
    )


@marshal_with(BeerItemSchema())
class BeerDetails(MethodResource):
    """
    Return details of a beer
    """

    @cache.cached(timeout=60)
    def get(self, slug):
        try:
            item = erp_client.query(ERPItem).get(
                slug,
                fields=[
                    "name",
                    "slideshow",
                    "description",
                    "disabled",
                    "item_code",
                    "web_long_description",
                    "website_specifications",
                    "thumbnail",
                    "website_image",
                ],
                filters=[
                    ["Item", "show_in_website", "=", "1"],
                    ["Item", "is_sales_item", "=", True],
                ],
            )
        except ERPItem.DoesNotExist:
            raise NotFound

        # If we have a slideshow, retrieve images
        if "slideshow" in item:
            try:
                slideshow = erp_client.query(ERPWebsiteSlideshow).get(item["slideshow"])
                item["slideshow_items"] = slideshow["slideshow_items"]
            except ERPWebsiteSlideshow.DoesNotExist:
                # There's no slideshow, we're fine
                pass

        return item


api_v1.register("/beers/<slug>", BeerDetails)
