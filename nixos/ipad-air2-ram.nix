# iPad Air 2 (J81): NixOS that lives entirely in RAM (netboot style: a squashfs Nix store plus a tmpfs root inside the initrd).
# Feasibility configuration, 2026-10-11 (docs/plans/2026-10-11-nixos-in-ram.md): no bootloader, no persistent storage (the internal NAND stays untouched),
# SSH key-only, the Wi-Fi tools. The kernel is NOT this configuration's: the m1n1 payload carries the Hoolock J81 kernel; here the NixOS kernel only exists so the
# system has no kernel or initrd of its own (round 3 of the size trim, 2026-10-12: the netboot module is gone; the squashfs of the store is built in flake.nix from the toplevel).
{ config, lib, pkgs, modulesPath, ... }:
let
  # The repo's own BusyBox-ash tools, copied one by one (not the whole boot directory) with their shebang pointing at the store's busybox.
  j81Tools = pkgs.runCommand "j81-tools" { } ''
    mkdir -p $out/bin
    install -m755 ${../boot/tablet-status.sh} $out/bin/tablet-status
    install -m755 ${../boot/tablet-dashboard.sh} $out/bin/tablet-dashboard
    install -m755 ${../boot/charging-policy.sh} $out/bin/charging-policy
    install -m755 ${../boot/power-diag.sh} $out/bin/power-diag
    for f in $out/bin/*; do sed -i '1s|.*|#!${pkgs.busybox}/bin/sh|' $f; done
  '';
in
{
  imports = [ ];

  nixpkgs.hostPlatform = "aarch64-linux";
  networking.hostName = "ipad-air2";
  networking.useDHCP = false;
  # USB-only, key-only ssh; the J81 kernel has no nftables/iptables modules to speak of, so no firewall unit that could fail.
  networking.firewall.enable = false;
  # The USB gadget (configfs ECM) is set up by stage 1 and survives switch_root; the Mac uses 172.16.42.2 statically.
  networking.interfaces.usb0.ipv4.addresses = [ { address = "172.16.42.1"; prefixLength = 24; } ];
  # Wi-Fi: stage 1 copies the private /etc/wpa_supplicant.conf and /lib/firmware into the new root (never from the network); brcmfmac is built in and already probed.
  systemd.services.wpa-supplicant-j81 = {
    description = "wpa_supplicant on wlan0 with the private configuration copied in by stage 1";
    wantedBy = [ "multi-user.target" ];
    after = [ "network-pre.target" ];
    unitConfig.ConditionPathExists = "/etc/wpa_supplicant.conf";
    serviceConfig = {
      ExecStart = "${pkgs.wpa_supplicant}/bin/wpa_supplicant -i wlan0 -D nl80211 -c /etc/wpa_supplicant.conf";
      Restart = "on-failure";
      RestartSec = 2;
    };
  };
  networking.interfaces.wlan0.useDHCP = true;

  services.openssh = {
    enable = true;
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "prohibit-password";
    };
  };
  users.users.root.openssh.authorizedKeys.keyFiles = [ ../boot/ssh/authorized_keys ];

  environment.systemPackages = (with pkgs; [ iw wpa_supplicant iproute2 busybox i2c-tools ]) ++ [ j81Tools ];

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
  # Stage 1's helpers do not survive the switch (they are killed by the hand-off), so the jobs they did become services here:
  # the charging policy (2400 mA input limit with backoff; without it the PMIC falls back to its 100 mA default) and the tablet dashboard on the screen.
  networking.usePredictableInterfaceNames = false;     # keep wlan0 (the scripts and the Wi-Fi unit use it)
  boot.kernel.sysctl."kernel.printk" = "1 1 1 1";      # kernel messages would overwrite the dashboard on the console
  # The screen shows the dashboard; ssh over USB is the way in. logind would otherwise spawn a getty on the active VT (it did on the first N2 boot), so no automatic VTs.
  systemd.services."getty@tty1".enable = false;
  services.logind.settings.Login = { NAutoVTs = 0; ReserveVT = 0; };
  systemd.services.charging-policy = {
    description = "J81 charging policy (input current limit with thermal and capacity backoff)";
    wantedBy = [ "multi-user.target" ];
    path = [ pkgs.busybox ];
    serviceConfig = {
      ExecStart = "${pkgs.busybox}/bin/sh ${j81Tools}/bin/charging-policy";
      StandardOutput = "append:/var/log/charging-policy.log";   # where power-diag and the stage-1 scripts look for it
      StandardError = "inherit";
      Restart = "on-failure";
      RestartSec = 5;
    };
  };
  systemd.services.tablet-dashboard = {
    description = "Tablet dashboard on the iPad screen";
    wantedBy = [ "multi-user.target" ];
    path = [ pkgs.busybox pkgs.iw j81Tools ];
    environment.DASH_COLS = "95";
    serviceConfig = {
      ExecStart = "${pkgs.busybox}/bin/sh ${j81Tools}/bin/tablet-dashboard --interval 5";
      StandardInput = "null";
      StandardOutput = "tty";
      StandardError = "null";
      TTYPath = "/dev/tty1";
      Restart = "always";
    };
  };
  system.stateVersion = "25.11";
}
