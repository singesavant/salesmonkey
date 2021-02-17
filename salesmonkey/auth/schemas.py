from salesmonkey import ma


class UserSchema(ma.Schema):
    username = ma.String(load_from="user")
    email = ma.Email(load_from="email")
    first_name = ma.String(load_from="first_name")
    last_name = ma.String(load_from="last_name")
