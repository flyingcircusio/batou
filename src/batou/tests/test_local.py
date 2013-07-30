from batou.local import main, deploy
import pytest
import sys


def test_no_args_exits_with_error(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['python'])
    with pytest.raises(SystemExit):
        main()


def test_local_deployment_with_hello_components(sample_service):
    deploy('test-multiple-hosts', '', 'localhost')
