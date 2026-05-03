# batou-stubs

Type stubs for the batou deployment library.

Install alongside batou so type checkers and editors can type-check your
deployment code:

    uv add --dev batou-stubs

No configuration needed: `batou-stubs` is a PEP 561 stub-only package, so
type checkers automatically resolve `import batou` through it. Each
batou-stubs release pins the exact matching batou version — stubs and
runtime cannot drift apart.

## Type-checking your deployment

ty and basedpyright pick up the installed stubs with no further
configuration: `ty check` or `basedpyright` should just work.
