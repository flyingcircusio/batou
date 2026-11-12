# batou-stubs

Type stubs for the batou deployment library.

Install alongside batou so type checkers and editors can type-check your
deployment code:

    uv add --dev batou-stubs

No configuration needed: `batou-stubs` is a PEP 561 stub-only package, so
type checkers automatically resolve `import batou` through it. Each
batou-stubs release pins the exact matching batou version — stubs and
runtime cannot drift apart.

## Development

The stubs live in `stubs/batou/`, mirroring `src/batou` one-to-one, and are
verified against the runtime package by mypy stubtest. See "Typed
development" in the main README for the full model.
