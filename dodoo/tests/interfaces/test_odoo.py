import psycopg2
import pytest

from dodoo.interfaces import odoo


class TestOdooInterface:
    def test_exceptions(self):
        odoo.Exceptions().AccessDenied

    def test_authentication(self):
        with pytest.raises(psycopg2.OperationalError):
            odoo.Authentication.authenticate("db", "login", "pwd")

    def test_logging(self):
        odoo.Logging().ColoredPerfFilter
        odoo.Logging().PerfFilter

    def test_wsgi(self):
        odoo.WSGI().app

    def test_regsitry(self):
        with pytest.raises(psycopg2.OperationalError):
            odoo.Registry("dbname")
        odoo.Registry.items()

    def test_environment(self):
        odoo.Environment("cr", "uid")

    def test_cron(self):
        odoo.Cron().acquire("dbname")

    def test_tools(self):
        odoo.Tools().resetlocale()
        odoo.Tools().lazy("obj")

    def test_modules(self):
        odoo.Modules().initialize_sys_path()
        odoo.Modules().MANIFEST_NAMES
        odoo.Modules().loaded
        odoo.Modules().load("base")
        odoo.Modules().deduce_module_name_from("path")
        odoo.Modules().deduce_module_and_relpath_from("path")
        odoo.Modules().parse_manifest_from("base")

    def test_database(self):
        odoo.Database().close_all()

    def test_config(self):
        odoo.Config().config
        odoo.Config().conf
        odoo.Config().defaults()

    def test_patchable(self):
        odoo.Modules().initialize_sys_path()
        odoo.Patchable.install_from_urls
        odoo.Patchable.update_notification
        odoo.Patchable.db_filter
        odoo.Patchable.ad_paths
        odoo.Patchable.get_modules
        odoo.Patchable.get_modules_with_version
        odoo.Patchable.exp_drop
        odoo.Patchable.exp_dump
        odoo.Patchable.exp_restore
        odoo.Patchable.connection_info_for
        odoo.Patchable.db_connect
        odoo.Patchable.verify_admin_password
        odoo.Patchable.exec_pg_command
        odoo.Patchable.exec_pg_command_pipe
        odoo.Patchable.exec_pg_environ
        odoo.Patchable.find_pg_tool