# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt

from __future__ import print_function, unicode_literals
from batou.host import Host
from batou.tests import TestCase
import multiprocessing


class InterlockedComponent(object):

    def __init__(self, lock1, lock2):
        self.lock1 = lock1
        self.lock2 = lock2

    def deploy(self):
        self.lock1.release()
        self.lock2.acquire()
        self.lock2.release()


class HostTest(TestCase):

    def test_host_should_create_lock(self):
        step1 = multiprocessing.Lock()
        step1.acquire()
        step2 = multiprocessing.Lock()
        step2.acquire()
        firsthost = Host('h1', 'env')
        firsthost.components.append(InterlockedComponent(step1, step2))
        t = multiprocessing.Process(target=firsthost.deploy)
        t.start()
        try:
            secondhost = Host('h2', 'env')
            step1.acquire()
            with self.assertRaises(RuntimeError):
                secondhost.deploy()
        finally:
            step1.release()
            step2.release()
            t.join()
