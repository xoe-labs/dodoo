#!/usr/bin/env dodoo shell

odoo = odoo  # noqa
env = env  # noqa
self = self  # noqa

admin = env["res.users"].search([("login", "=", "admin")])
admin.login = "newadmin"

raise Exception()