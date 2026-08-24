- Replace the GPG test fixtures with self-generated, never-expiring
  fixture keys (`ct@example.com` / `cz@example.com`) instead of real,
  potentially expiring keys. The new `regenerate-gpg-fixtures.sh` script
  regenerates keys, signatures, and all encrypted fixture files in one
  step.
