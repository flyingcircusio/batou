from batou.lib.debian import LogrotateCronjob, Logrotate
from batou.lib.debian import RebootCronjob, Supervisor
from batou.lib.service import Service

# This is a very rough test to at least ensure we can import the modules
# and trigger configure() runs for the components


def test_rebootcronjob(root):
    service = Service('bobbob')
    cronjob = RebootCronjob()
    root.component += service
    service += cronjob


def test_supervisor(root):
    s = Supervisor()
    root.component += s


def test_logrotatecronjob(root):
    cronjob = LogrotateCronjob()
    root.component += cronjob
    logrotate = Logrotate()
    cronjob += logrotate
