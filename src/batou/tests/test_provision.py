def test_fc_dev_vm_provisioner_exists():
    # "FCDevVM" is used as a lookup key and must not be accidentally
    # changed. Unfortunately we don't have better provisioning tests
    # at the moment that ensures the consistency through an
    # end-to-end test.
    from batou.provision import FCDevVM, Provisioner

    assert issubclass(FCDevVM, Provisioner)
