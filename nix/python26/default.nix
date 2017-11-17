{ stdenv, pkgs, zlib, bzip2, file, openssl, darwin }:

stdenv.mkDerivation {
  name = "python-2.6.9";
  src = pkgs.fetchurl {
    url = "https://www.python.org/ftp/python/2.6/Python-2.6.9.tar.xz";
    sha256 = "0hbfs2691b60c7arbysbzr0w9528d5pl8a4x7mq5psh6a2cvprya";
  };

  buildInputs = [ zlib.dev bzip2.dev file openssl 
      darwin.apple_sdk.frameworks.Foundation
      darwin.apple_sdk.frameworks.SystemConfiguration ];

  preConfigure = ''
    export LDFLAGS="-L${openssl.dev}/lib"
    export CFLAGS="-I${openssl.dev}/include"
  '';

  configureFlags = [
    "--disable-toolbox-glue"
    "--without-tcl"
  ];

}