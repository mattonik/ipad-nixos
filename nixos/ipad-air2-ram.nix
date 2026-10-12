# iPad Air 2 (J81): NixOS that lives entirely in RAM (netboot style: a squashfs Nix store plus a tmpfs root inside the initrd).
# Feasibility configuration, 2026-10-11 (docs/plans/2026-10-11-nixos-in-ram.md): no bootloader, no persistent storage (the internal NAND stays untouched),
# SSH key-only, the Wi-Fi tools. The kernel is NOT this configuration's: the m1n1 payload carries the Hoolock J81 kernel; here the NixOS kernel only exists so the
# system has no kernel or initrd of its own (round 3 of the size trim, 2026-10-12: the netboot module is gone; the squashfs of the store is built in flake.nix from the toplevel).
{ config, lib, pkgs, modulesPath, ... }:
{
  imports = [ ];

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
  # Round 2 of the size trim (2026-10-11): perl comes from switch-to-configuration (a RAM-only system is never switched), groff from man pages, file from nano.
  system.switch.enable = false;
  documentation.man.enable = false;
  documentation.nixos.enable = false;
  programs.nano.enable = lib.mkForce false;
  services.lvm.enable = false;
  boot.swraid.enable = lib.mkForce false;
  # Round 3: no kernel, no initrd, no bootloader. The m1n1 payload brings the Hoolock J81 kernel; stage 1 (boot/nixos-handoff.sh) mounts the store and runs the toplevel's init.
  boot.kernel.enable = false;
  boot.initrd.enable = false;
  boot.loader.grub.enable = false;
  boot.bootspec.enable = false;
  fileSystems."/" = { device = "none"; fsType = "tmpfs"; options = [ "mode=0755" ]; };
  system.stateVersion = "25.11";
}
