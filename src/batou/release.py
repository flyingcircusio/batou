from zest.releaser.utils import system
import logging
import os

logger = logging.getLogger(__name__)


def update_requirements(data):
    os.chdir(data['workingdir'])
    logger.info('Running buildout to update requirements.txt.')
    system('bin/buildout')
    logger.info('Committing requirements.txt.')
    system('hg commit -v -m "Update requirements.txt"')
