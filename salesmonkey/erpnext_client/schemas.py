from marshmallow import Schema, fields


class ERPDocument(Schema):
    """
    Base ERPNext Document
    """
    name = fields.String()


class ERPUserSchema(ERPDocument):
    email = fields.Email(load_from="email")
    first_name = fields.String(load_from="first_name")
    last_name = fields.String(load_from="last_name")


class ERPItemSchema(ERPDocument):
    code = fields.String(load_from="item_code")
    name = fields.String(load_from="item_name")
    disabled = fields.Boolean(load_from="disabled")
    description_html = fields.String(load_from="description")
    website_long_description_html = fields.String(load_from='web_long_description')
    price = fields.Float(load_from='standard_rate')
    total_projected_qty = fields.Float(load_from='total_projected_qty')
    thumbnail = fields.String()


class ERPItemGroupSchema(ERPDocument):
    name = fields.String(load_from="name")


class ERPCustomerSchema(ERPDocument):
    email = fields.Email(load_from="email")


class ERPContactSchema(ERPDocument):
    email = fields.Email(load_from="email_id")
    first_name = fields.String(load_from="first_name")
    last_name = fields.String(load_from="last_name")


class ERPDynamicLinkSchema(ERPDocument):
    """
    Dynamic Link between two documents
    """
    link_name = fields.String(load_from="link_name")
    parent = fields.String(load_from="parent")
    parent_type = fields.String(load_from="parenttype")

class ERPSalesOrderItemSchema(ERPDocument):
    item_code = fields.String()
    item_name = fields.String()
    description = fields.String()
    quantity = fields.Int(load_from="qty")
    rate = fields.Float()
    amount = fields.Float(load_from="net_amount")


class ERPSalesOrderSchema(ERPDocument):
    date = fields.Date(load_from="transaction_date")
    title = fields.Str()
    customer = fields.Str()
    amount_total = fields.Float(load_from="grand_total")
    items = fields.Nested(ERPSalesOrderItemSchema, many=True)
