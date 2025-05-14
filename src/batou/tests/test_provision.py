import batou.provision


def test_fc_dev_vm_provisioner_exists():
    # "FCDevVM" is used as a lookup key and must not be accidentally
    # changed. Unfortunately we don't have better provisioning tests
    # at the moment that ensures the consistency through an
    # end-to-end test.
    assert issubclass(batou.provision.FCDevVM, batou.provision.Provisioner)


def test_fc_dev_vm_provisioner_from_config():
    from batou.provision import FCDevVM

    provisioner = FCDevVM.from_config_section(
        "foobar",
        {
            "host": "dummy",
            "memory": "8192",
            "cores": "1",
            "release": "https://my.flyingcircus.io/releases/metadata/fc-24.05-production/2025_006",
        },
    )

    assert provisioner.target_host == "dummy"
    assert provisioner.memory == "8192"
    assert provisioner.cores == "1"
    assert (
        provisioner.channel_url
        == "https://hydra.flyingcircus.io/build/4385779/download/1/nixexprs.tar.xz"
    )
    assert (
        provisioner.image_url
        == "https://hydra.flyingcircus.io/build/4385780/download/1"
    )
