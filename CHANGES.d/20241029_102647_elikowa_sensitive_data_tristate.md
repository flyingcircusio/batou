- `File` Component: Converted `sensitive_data` flag to a tri-state variable. This allows manual overriding of automatic sensitivity detection logic for file diffs. The new possible states are:
  - `None`: Default automatic detection of sensitive data.
  - `True`: Always mark the file as sensitive and avoid printing the diff.
  - `False`: Always print the file diff, even if sensitive data is detected.