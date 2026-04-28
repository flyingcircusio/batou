def add_user(
    keyid: str,
    environments: str,
    **kw: object,
) -> None: ...
def decrypt_to_stdout(file: str) -> int: ...
def reencrypt(
    environments: str,
    force: bool = ...,
    **kw: object,
) -> None: ...
def remove_user(
    keyid: str,
    environments: str,
    **kw: object,
) -> None: ...
def summary() -> int: ...
