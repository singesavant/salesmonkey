from marshmallow import Schema, fields


class ERPDocument(Schema):
    """
    Base ERPNext Document
    """
    name = fields.String()


class ERPItemSchema(ERPDocument):
    code = fields.String(load_from="item_code")
    name = fields.String(load_from="item_name")
    description_html = fields.String(load_from="description")
    long_description_html = fields.String(load_from='web_long_description')
    price = fields.Float(load_from='standard_rate')
    thumbnail = fields.String()


class ERPCustomerSchema(ERPDocument):
    pass


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
