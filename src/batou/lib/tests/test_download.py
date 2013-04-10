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

    def test_configure_should_raise_valueerror_if_no_checksum_given(self):
        from ..download import Download
        download = Download('url')
        with self.assertRaises(ValueError) as exc:
            download.configure()
        self.assertEqual('No checksum given.', exc.exception.args[0])

    def test_update_should_raise_AssertionError_on_checksum_mismatch(self):
        from ..download import Download
        download = Download('url', checksum='foobar:1234')
        download.configure()
        with mock.patch('batou.lib.download.Download.cmd'), \
             mock.patch('batou.utils.hash') as buh,\
             self.assertRaises(AssertionError) as err:
            buh.return_value = '4321'
            download.update()
        self.assertEqual('Checksum mismatch!\nexpected: 1234\ngot: 4321',
                         str(err.exception))

