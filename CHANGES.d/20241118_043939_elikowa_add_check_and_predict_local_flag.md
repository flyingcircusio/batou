    <!-- p.add_argument(
        "--check-and-predict-local",
        action="store_true",
        help="When running in consistency-only or predict-only mode, "
        "do not connect to the remote host, but check and predict "
        "using the local host's state.",
    ) -->
- Adds a `--check-and-predict-local` flag to `./batou deploy`, which can
  be used in tandem with `--consistency-only` or `--predict-only` to
  check and predict using the local host's state, without connecting to
  the remote host.
