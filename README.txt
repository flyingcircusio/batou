=====
batou
=====

Batou is a tool to deploy services consisting of interacting components for
development and production environments.

Working with batou consists of two steps:

* **defining services**


* **deploying services**


Defining a service
==================

Services are defined by describing the components they are made up of as
Python code that will be run during a deployment and by specifying the
environments in which the components will be deployed.

Batou gives you a structure for arranging your components and a library that
makes it easy to write components.

Component definition
--------------------

Components are pieces of software whose configuration depends on the
environment and host their are configured on as well as the configuration of
other components.

Here's a component that touches a file::

  class Touch(Component):
     @step(1)
     def touch(self):
        self.cmd('touch /tmp/asdf')

Environments
------------

Environments provide configuration to components and select which components
should be installed on which hosts.

Here's an environment definition that would be suitable for development::

   [hosts]
   localhost = touch


Deploying a service
===================


Locally
-------

You can deploy any configuration locally that you want. In the most simple
case you select your devel



Remotely
--------







In-depth
========

The sizing of a component depends on two factors: coherence and distribution.
If some software is always build together and/or shares a lot of build code,
it should be a single component or depend on a shared component. If software
needs to be run on different hosts independently it should be split in
multiple components or make use "features" to control partial configurations
with shared code.


Other topics
============

* deployment into service user
* code push/bouncing
* check in multiple development environments (per developer)
* run a production deployment locally for debugging
* use secrets management
* use templating (inline, files)
    * jinja
    * mako
* use base components
    * haproxy
    * buildout
* use hooks
* use features
* make stuff convergent
* host name normalization
* cross-environment protection
* component API
* config helpers
    * address objects
    * netloc objects

