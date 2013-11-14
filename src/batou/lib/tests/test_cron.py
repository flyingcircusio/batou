from ..cron import CronJob, CronTab
import batou.vfs
import os.path


def test_collects_cronjobs_into_crontab(root):
    root.environment.vfs_sandbox = batou.vfs.Developer(root.environment, None)
    root.component += CronJob('command1', timing='* * * * *')
    root.component += CronJob('command2', timing='* * * * *')
    root.component += CronTab()
    root.component.deploy()
    crontab = open(os.path.join(
        root.environment.workdir_base, 'mycomponent/crontab')).read()
    assert 'command1' in crontab
    assert 'command2' in crontab
