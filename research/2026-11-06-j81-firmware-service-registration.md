# J81 firmware service-registration boundary

The generic AGX publisher at `0xffffff8002665130` resolves the concrete
firmware-object calls using the extracted `AGXFirmwareKextG4G` vtable:

- firmware object `+0x358` (`vptr 0xffffff8002e50080`) is
  `IOService::attach(parent)`;
- firmware object `+0x298` is `IOService::registerService(0)`;
- the preceding object creation comes from accelerator vtable `+0x570`.

The publisher stores the attached object, then registers it. That registration
is the likely handoff that causes IOKit to start/match the firmware service;
there is no direct GPU MMIO or firmware-execution call in this publisher.
The J81 descriptor routine's final `+0xc0` call remains a separate property
publication operation. The next offline target is the IOKit start/match path
for `AGXFirmwareKextG4G`, not another raw GPU register read.
