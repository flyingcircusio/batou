from batou.local import main


def test_local_deployment_with_hello_components(sample_service):
    main('test-multiple-hosts', 'localhost', '', None)
