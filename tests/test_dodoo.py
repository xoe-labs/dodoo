# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from __future__ import print_function

import os
import subprocess
import textwrap

import click
import psycopg2
import pytest
from click.testing import CliRunner

from dodoo import CommandWithOdooEnv, OdooEnvironment, console, odoo, odoo_bin, options
from dodoo.cli import main

here = os.path.abspath(os.path.dirname(__file__))

# This hack is necessary because the way CliRunner patches
# stdout is not compatible with the Odoo logging initialization
# mechanism. Logging is therefore tested with subprocesses.
odoo.netsvc._logger_init = True


def _init_odoo_db(dbname):
    subprocess.check_call(["createdb", dbname])
    subprocess.check_call([odoo_bin, "-d", dbname, "-i", "base", "--stop-after-init"])


def _drop_db(dbname):
    subprocess.check_call(["dropdb", "--if-exists", dbname])


@pytest.fixture(scope="session")
def odoodb():
    if "DODOO_TEST_DB" in os.environ:
        yield os.environ["DODOO_TEST_DB"]
    else:
        dbname = "dodoo-test-" + odoo.release.version.replace(".", "-")
        try:
            _init_odoo_db(dbname)
            yield dbname
        finally:
            _drop_db(dbname)


def test_odoo_env(odoodb, mocker):
    self = mocker.patch("dodoo.CommandWithOdooEnv")
    self.database = odoodb
    with OdooEnvironment(self) as env:
        admin = env["res.users"].search([("login", "=", "admin")])
        assert len(admin) == 1


def test_dodoo(odoodb):
    """ Test simple access to env in script """
    script = os.path.join(here, "scripts", "script1.py")
    cmd = ["dodoo", "run", "-d", odoodb, script]
    result = subprocess.check_output(cmd, universal_newlines=True)
    assert result == "admin\n"


def test_cli_runner(odoodb):
    """ Test simple access to env in script (through click CliRunner) """
    script = os.path.join(here, "scripts", "script1.py")
    runner = CliRunner()
    result = runner.invoke(main, ["run", "-d", odoodb, script])
    assert result.exit_code == 0
    assert result.output == "admin\n"


def test_dodoo_args(odoodb):
    """ Test sys.argv in script """
    script = os.path.join(here, "scripts", "script2.py")
    cmd = ["dodoo", "run", "-d", odoodb, "--", script, "a", "-b", "-d"]
    result = subprocess.check_output(cmd, universal_newlines=True)
    assert result == textwrap.dedent(
        """\
        sys.argv = {} a -b -d
        __name__ = __main__
    """.format(
            script
        )
    )


def test_interactive_no_script(mocker, odoodb):
    mocker.patch.object(console.Shell, "ipython")
    mocker.patch.object(console.Shell, "python")
    mocker.patch.object(console, "_isatty", return_value=True)

    runner = CliRunner()
    result = runner.invoke(main, ["run", "-d", odoodb])
    assert result.exit_code == 0
    assert console.Shell.ipython.call_count == 1
    assert console.Shell.python.call_count == 0


def test_interactive_no_script_preferred_shell(mocker, odoodb):
    mocker.patch.object(console.Shell, "ipython")
    mocker.patch.object(console.Shell, "python")
    mocker.patch.object(console, "_isatty", return_value=True)

    runner = CliRunner()
    result = runner.invoke(main, ["run", "-d", odoodb, "--shell-interface=python"])
    assert result.exit_code == 0
    assert console.Shell.ipython.call_count == 0
    assert console.Shell.python.call_count == 1


def test_auto_env_prefix(mocker, odoodb):
    mocker.patch.object(console.Shell, "ipython")
    mocker.patch.object(console.Shell, "python")
    mocker.patch.object(console, "_isatty", return_value=True)

    runner = CliRunner()
    result = runner.invoke(
        main, ["run", "-d", odoodb], env={"DODOO_RUN_SHELL_INTERFACE": "python"}
    )
    assert result.exit_code == 0
    assert console.Shell.ipython.call_count == 0
    assert console.Shell.python.call_count == 1


def test_logging_stderr(capfd, odoodb):
    script = os.path.join(here, "scripts", "script3.py")
    cmd = ["dodoo", "run", "-d", odoodb, "--", script]
    subprocess.check_call(cmd)
    out, err = capfd.readouterr()
    assert not out
    assert "Modules loaded" in err
    assert "hello from script3" in err


def test_logging_logfile(tmpdir, capfd, odoodb):
    script = os.path.join(here, "scripts", "script3.py")
    logfile = tmpdir.join("mylogfile")
    cmd = ["dodoo", "run", "-d", odoodb, "--logfile", str(logfile), "--", script]
    subprocess.check_call(cmd)
    out, err = capfd.readouterr()
    assert not out
    logcontent = logfile.read()
    assert "Modules loaded" in logcontent
    assert "hello from script3" in logcontent


def test_withdb(odoodb, tmpdir):
    @click.command(cls=CommandWithOdooEnv)
    @options.db_opt(True)
    def testcmd(env):
        login = env["res.users"].search([("login", "=", "admin")]).login
        click.echo("login={}".format(login))

    # database from command line
    runner = CliRunner()
    result = runner.invoke(testcmd, ["-d", odoodb])
    assert result.exit_code == 0
    assert "login=admin\n" in result.output
    # database in config
    odoocfg1 = tmpdir / "odoo1.cfg"
    odoocfg1.write(
        textwrap.dedent(
            """\
        [options]
        db_name={}
    """.format(
                odoodb
            )
        )
    )
    result = runner.invoke(testcmd, ["-c", str(odoocfg1)])
    assert result.exit_code == 0
    assert "login=admin\n" in result.output
    # database -d has priority over db_name in config
    odoocfg2 = tmpdir / "odoo2.cfg"
    odoocfg2.write(
        textwrap.dedent(
            """\
        [options]
        db_name=notadb
    """
        )
    )
    result = runner.invoke(testcmd, ["-c", str(odoocfg2), "-d", odoodb])
    assert result.exit_code == 0
    assert "login=admin\n" in result.output
    # no -d, error
    odoo.tools.config["db_name"] = None  # Reset the defaulting mechanism
    result = runner.invoke(testcmd, [])
    assert result.exit_code != 0
    assert 'Missing option "--database"' in result.output


def test_nodb(odoodb, tmpdir):
    @click.command(cls=CommandWithOdooEnv)
    def testcmd(env):
        assert not env

    # no database
    runner = CliRunner()
    result = runner.invoke(testcmd, [])
    assert result.exit_code == 0
    # -d not allowed
    result = runner.invoke(testcmd, ["-d", odoodb])
    assert result.exit_code != 0
    assert "no such option: -d" in result.output
    # db_name in config ignored
    odoocfg1 = tmpdir / "odoo1.cfg"
    odoocfg1.write(
        textwrap.dedent(
            """\
        [options]
        db_name={}
    """.format(
                odoodb
            )
        )
    )
    result = runner.invoke(testcmd, ["-c", str(odoocfg1)])
    assert result.exit_code == 0


def test_optionaldb(odoodb, tmpdir):
    @click.command(cls=CommandWithOdooEnv)
    @options.db_opt(False)
    def testcmd(env):
        if env:
            print("with env")
        else:
            print("without env")

    # no database
    runner = CliRunner()
    odoo.tools.config["db_name"] = None  # Reset the defaulting mechanism
    result = runner.invoke(testcmd, [])
    assert result.exit_code == 0
    assert "without env" in result.output
    # with database
    runner = CliRunner()
    result = runner.invoke(testcmd, ["-d", odoodb])
    assert result.exit_code == 0
    assert "with env" in result.output
    # database in config
    odoocfg1 = tmpdir / "odoo1.cfg"
    odoocfg1.write(
        textwrap.dedent(
            """\
        [options]
        db_name={}
    """.format(
                odoodb
            )
        )
    )
    result = runner.invoke(testcmd, ["-c", str(odoocfg1)])
    assert result.exit_code == 0
    assert "with env" in result.output


def test_env_options_database_must_exist(odoodb):
    @click.command(cls=CommandWithOdooEnv, env_options={"database_must_exist": False})
    @options.db_opt(True)
    def testcmd(env):
        if env:
            print("with env")
        else:
            print("without env")

    @click.command(cls=CommandWithOdooEnv)
    @options.db_opt(True)
    def testcmd_must_exist(env):
        pass

    # no database, must not exist, no env
    runner = CliRunner()
    result = runner.invoke(testcmd, ["-d", "dbthatdoesnotexist"])
    assert result.exit_code == 0
    assert "without env" in result.output

    # no database, must exist, error
    runner = CliRunner()
    result = runner.invoke(testcmd_must_exist, ["-d", "dbthatdoesnotexist"])
    assert result.exit_code != 0
    assert (
        "The provided database does not exists and this script requires"
        in result.output
    )

    # database exists, must not exist, env ok
    runner = CliRunner()
    result = runner.invoke(testcmd, ["-d", odoodb])
    assert result.exit_code == 0
    assert "with env" in result.output


def _cleanup_testparam(dbname):
    with psycopg2.connect(dbname=dbname) as conn:
        with conn.cursor() as cr:
            cr.execute("DELETE FROM ir_config_parameter " "WHERE key='testparam'")
            conn.commit()
    conn.close()


def _assert_testparam_present(dbname, expected):
    with psycopg2.connect(dbname=dbname) as conn:
        with conn.cursor() as cr:
            cr.execute("SELECT value FROM ir_config_parameter " "WHERE key='testparam'")
            r = cr.fetchall()
            assert len(r) == 1
            assert r[0][0] == expected
    conn.close()


def _assert_testparam_absent(dbname):
    with psycopg2.connect(dbname=dbname) as conn:
        with conn.cursor() as cr:
            cr.execute("SELECT value FROM ir_config_parameter " "WHERE key='testparam'")
            r = cr.fetchall()
            assert len(r) == 0
    conn.close()


def test_write_commit_in_script(odoodb):
    """ test commit in script """
    _cleanup_testparam(odoodb)
    script = os.path.join(here, "scripts", "script4.py")
    cmd = ["dodoo", "run", "-d", odoodb, "--", script, "commit"]
    subprocess.check_call(cmd)
    _assert_testparam_present(odoodb, "testvalue")


def test_write_rollback_in_script(odoodb):
    """ test rollback in script """
    _cleanup_testparam(odoodb)
    script = os.path.join(here, "scripts", "script4.py")
    cmd = ["dodoo", "run", "-d", odoodb, "--", script, "rollback"]
    subprocess.check_call(cmd)
    _assert_testparam_absent(odoodb)


def test_write_defaulttx(odoodb):
    """ test dodoo commits itself """
    _cleanup_testparam(odoodb)
    script = os.path.join(here, "scripts", "script4.py")
    cmd = ["dodoo", "run", "-d", odoodb, "--", script]
    subprocess.check_call(cmd)
    _assert_testparam_present(odoodb, "testvalue")


def test_write_rollback(odoodb):
    """ test dodoo rollbacks itself """
    _cleanup_testparam(odoodb)
    script = os.path.join(here, "scripts", "script4.py")
    cmd = ["dodoo", "run", "--rollback", "-d", odoodb, "--", script]
    subprocess.check_call(cmd)
    _assert_testparam_absent(odoodb)


def test_write_default_rollback(odoodb):
    """ test dodoo rollbacks itself via default_map """
    _cleanup_testparam(odoodb)

    @click.command(
        cls=CommandWithOdooEnv, context_settings=dict(default_map={"rollback": True})
    )
    @options.rollback_opt()
    def testcmd(env):
        env = env  # noqa
        env["ir.config_parameter"].set_param("testparam", "testvalue")

    runner = CliRunner()
    runner.invoke(testcmd, ["-d", odoodb])
    _assert_testparam_absent(odoodb)


def test_write_interactive_defaulttx(mocker, odoodb):
    """ test dodoo rollbacks in interactive mode """
    mocker.patch.object(console.Shell, "python")
    mocker.patch.object(console, "_isatty", return_value=True)

    _cleanup_testparam(odoodb)
    runner = CliRunner()
    script = os.path.join(here, "scripts", "script4.py")
    cmd = ["run", "-d", odoodb, "--interactive", "--", script]
    result = runner.invoke(main, cmd)
    assert result.exit_code == 0
    _assert_testparam_absent(odoodb)


def test_write_stdin_defaulttx(odoodb):
    _cleanup_testparam(odoodb)
    script = os.path.join(here, "scripts", "script4.py")
    cmd = ["dodoo", "run", "-d", odoodb, "<", script]
    subprocess.check_call(" ".join(cmd), shell=True)
    _assert_testparam_present(odoodb, "testvalue")


def test_write_raise(tmpdir, capfd, odoodb):
    """ test nothing is committed if the script raises """
    _cleanup_testparam(odoodb)
    script = os.path.join(here, "scripts", "script4.py")
    logfile = tmpdir.join("mylogfile")
    cmd = [
        "dodoo",
        "run",
        "-d",
        odoodb,
        "--logfile",
        str(logfile),
        "--",
        script,
        "raise",
    ]
    r = subprocess.call(cmd)
    assert r != 0
    logcontent = logfile.read()
    assert "testerror" in logcontent
    our, err = capfd.readouterr()
    assert "testerror" in err
    _assert_testparam_absent(odoodb)


def test_env_cache(odoodb, mocker):
    """ test a new environment does not reuse cache """
    _cleanup_testparam(odoodb)
    self = mocker.patch("dodoo.CommandWithOdooEnv")
    self.database = odoodb
    with OdooEnvironment(self) as env:
        env["ir.config_parameter"].set_param("testparam", "testvalue")
        value = env["ir.config_parameter"].get_param("testparam")
        assert value == "testvalue"
        env.cr.commit()
    _assert_testparam_present(odoodb, "testvalue")
    _cleanup_testparam(odoodb)
    _assert_testparam_absent(odoodb)
    with OdooEnvironment(self) as env:
        value = env["ir.config_parameter"].get_param("testparam")
        assert not value


def test_addons_path():
    script = os.path.join(here, "scripts", "script5.py")

    cmd = ["dodoo", "run", "--", script]
    r = subprocess.call(cmd)
    assert r != 0  # addon1 not found in addons path

    addons_path = ",".join(
        [
            os.path.join(odoo.__path__[0], "addons"),
            os.path.join(os.path.dirname(__file__), "data", "addons"),
        ]
    )

    cmd = ["dodoo", "run", "--addons-path", addons_path, "--", script]
    r = subprocess.call(cmd)
    assert r == 0