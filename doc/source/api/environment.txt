Environment configuration
=========================

Component assignment (TODO)
---------------------------

General parameters (TODO)
-------------------------

General environment parameters are set in the ``[environment]`` config section.
Example::

    [environment]
    service_user = website
    host_domain = gocept.net
    platform = gocept
    branch = production

service_user
    The deployment is run as this user on remote machines. If this is not
    the same as the user connecting via ssh, a `sudo` to the service user
    is performed.

host_domain
    All hosts in the ``[hosts]`` section are postfixed with this domain. This
    is handy do make the host/component assignment less verbose

update_method
    `hg-bundle|hg-pull|git-bundle|git-pull|rsync`, sets how the remote deployment repository is updated.

    * `pull`, the default, uses `hg/git clone` and/or `hg/git pull` on the remote site.
    * `bundle` will copy the necessary changes as Mercurial/Git bundle, via the batou ssh link.
    * `rsync` will rsync the *working copy*. This is most useful in combination with the vagrant platform.


branch
    For remote deployments, use this and only this branch. batou will
    complain if the local branch does not match the set branch in the
    environment.

platform
    Set the platform for this environment.

timeout
    Set the ssh connection timeout in seconds.

target_directory
        Absolute path of the directory on remote machines where the remote
        deployment repository is stored. Supports tilde expansion. Default:
        ``~/deployment``.


vfs mapping (TODO)
------------------

Root-component attribute overrides (TODO)
------------------------------------------
