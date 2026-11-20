_: {
  flake.modules.nixos.arduino =
    { pkgs, ... }:
    {
      # Serial access comes from colin's dialout group (common.nix).
      environment.systemPackages = with pkgs; [
        arduino-ide
        arduino-cli
      ];
    };
}
