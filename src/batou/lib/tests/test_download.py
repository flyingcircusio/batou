import mock
import unittest


class DownloadTest(unittest.TestCase):

    def test_verify_should_pass_checkum_function_to_hash(self):
        import batou
        from ..download import Download
        component = Download('url', checksum='foobar:1234')
        component.configure()
        with mock.patch('os.path.exists') as exists,\
                mock.patch('batou.utils.hash') as buh:
            exists.return_value = True
            try:
                component.verify()
            except batou.UpdateNeeded:
                pass
        buh.assert_called_with(mock.ANY, 'foobar')
