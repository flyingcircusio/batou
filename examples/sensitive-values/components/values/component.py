from batou.component import Component
from batou.lib.file import File


class SensitiveValues(Component):

    # SSH keys loaded from age-encrypted secrets
    ssh_client_privkey = None
    ssh_client_pubkey = None

    # SSH keys loaded from plaintext configuration
    ssh_host_rsa_pubkey = None
    ssh_host_ed25519_pubkey = None

    def configure(self):
        # File content loaded from secrets automatically detected as
        # sensitive.
        self += File(
            "client_ed25519.key",
            content="{{component.ssh_client_privkey}}",
        )
        self += File(
            "client_ed25519.pub",
            content="{{component.ssh_client_pubkey}}",
        )

        # Content from non-secret configuration automatically marked
        # sensitive when words overlap with words found in secret
        # values.
        self += File(
            "hostkey_sensitive_auto_rsa.pub",
            content="{{component.ssh_host_rsa_pubkey}}",
        )
        self += File(
            "hostkey_sensitive_auto_ed25519.pub",
            content="{{component.ssh_host_ed25519_pubkey}}",
        )

        # Override autodetection of file content sensitivity.
        self += File(
            "hostkey_sensitive_masked_rsa.pub",
            content="{{component.ssh_host_rsa_pubkey}}",
            sensitive_data=True,
        )
        self += File(
            "hostkey_sensitive_clear_ed25519.pub",
            content="{{component.ssh_host_ed25519_pubkey}}",
            sensitive_data=False,
        )
