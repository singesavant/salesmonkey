from marshmallow import Schema, fields


class ERPDocument(Schema):
    """
    Base ERPNext Document
    """
    name = fields.String(attribute='name')


class ERPItemSchema(ERPDocument):
    code = fields.String(attribute="item_code")
    name = fields.String(attribute="item_name")
    description = fields.String(attribute='web_long_description')
    price = fields.Float(attribute='standard_rate')
    thumbnail = fields.String(attribute='thumbnail')


class ERPCustomerSchema(ERPDocument):
    name = fields.String(attribute="name")


class ERPSalesOrderItemSchema(ERPDocument):
    item_code = fields.String()
    item_name = fields.String()
    description = fields.String()
    quantity = fields.Int(attribute="qty")
    rate = fields.Float()
    amount = fields.Float(attribute="net_amount")


class ERPSalesOrderSchema(ERPDocument):
    name = fields.String(attribute="name")
    date = fields.DateTime(attribute="transaction_date")
    title = fields.String(attribute="title")
    customer = fields.String()
    amount_total = fields.Float(attribute="grand_total")
    items = fields.Nested(ERPSalesOrderItemSchema, many=True)
