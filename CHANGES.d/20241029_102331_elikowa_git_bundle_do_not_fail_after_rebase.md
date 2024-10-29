- When shipping a repository to the remote host using `git-bundle`, previously, when
  the history of the repository was rewritten, the bundle would fail to be created, due
  to the remote `HEAD` not being a predecessor of the local `HEAD`. This has been fixed
  by creating the bundle using the whole branch history, instead of just the changes between
  remote `HEAD` and branch `HEAD` when the remote `HEAD` is not a part of the branch.
