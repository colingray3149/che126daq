{
  description = "Local command-first ChE 126 serial DAQ hub";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { nixpkgs, ... }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    python = pkgs.python3.withPackages (p: [ p.aiohttp p.pyserial p.plotly p.kaleido ]);
    hub = pkgs.writeShellApplication {
      name = "che126daq";
      text = ''
        exec ${python}/bin/python ${./host}/hub.py \
          --config "''${CHE126DAQ_CONFIG:-$HOME/Projects/che126daq/hub.toml}" "$@"
      '';
    };
  in {
    packages.${system}.default = hub;
    apps.${system}.default = { type = "app"; program = "${hub}/bin/che126daq"; };
    devShells.${system}.default = pkgs.mkShell { packages = [ python ]; };
  };
}
