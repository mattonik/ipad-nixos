# iPad Air 2 (J81): NixOS that lives entirely in RAM (netboot style: a squashfs Nix store plus a tmpfs root inside the initrd).
# Feasibility configuration, 2026-10-11 (docs/plans/2026-10-11-nixos-in-ram.md): no bootloader, no persistent storage (the internal NAND stays untouched),
# SSH key-only, the Wi-Fi tools. The kernel is NOT this configuration's: the m1n1 payload carries the Hoolock J81 kernel; here the NixOS kernel only exists so the
# netboot module can build an initrd for size measurement (system.build.netbootRamdisk).
{ config, lib, pkgs, modulesPath, ... }:
{
  imports = [ "${modulesPath}/installer/netboot/netboot.nix" ];

  nixpkgs.hostPlatform = "aarch64-linux";
  networking.hostName = "ipad-air2";
  networking.useDHCP = false;
  networking.firewall.enable = true;

  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "prohibit-password";
    };
  };
  users.users.root.openssh.authorizedKeys.keyFiles = [ ../boot/ssh/authorized_keys ];

  environment.systemPackages = with pkgs; [ iw wpa_supplicant iproute2 busybox ];

  # Keep the closure small: this is a RAM-resident system on a 2 GB tablet.
  documentation.enable = false;
  programs.command-not-found.enable = false;
  nix.enable = false;
  boot.enableContainers = false;
  environment.defaultPackages = [ ];
  services.udisks2.enable = false;
  security.polkit.enable = lib.mkForce false;
  fonts.fontconfig.enable = false;
  system.stateVersion = "25.11";
}
