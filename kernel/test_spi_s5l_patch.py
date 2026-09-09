#!/usr/bin/env python3
"""Guard the S5L SPI fixes that must hold before TOUCH-1 is built."""

from pathlib import Path


patch = Path(__file__).with_name("patches").joinpath(
    "0007-spi-apple-add-s5l8960x-support.patch"
).read_text()
irq = patch[
    patch.index("+static irqreturn_t apple_s5l_spi_irq") : patch.index(
        " static irqreturn_t apple_spi_irq"
    )
]
wait = patch[
    patch.index("+static int apple_s5l_spi_wait") : patch.index(
        " static int apple_spi_wait"
    )
]

assert "device->mode & SPI_LSB_FIRST ? 0 : APPLE_S5L_SPI_CFG_MSB_FIRST" in patch
assert "device->mode & SPI_LSB_FIRST ? APPLE_SPI_CFG_LSB_FIRST : 0" in patch
assert irq.index("+\t\tretval = IRQ_HANDLED;") < irq.index("+\t\tcomplete(&spi->done);")
assert wait.index("+\t\treinit_completion(&spi->done);") < wait.rindex(
    "+\t\treg_mask(spi, APPLE_SPI_CFG, APPLE_SPI_CFG_MODE"
)
assert wait.count("+\t\treg_mask(spi, APPLE_SPI_CFG, APPLE_S5L_SPI_CFG_IE_FLAGS, 0);") == 2
assert "+\t\twords = read = FIELD_GET(APPLE_S5L_SPI_STATUS_RXFIFO," in patch

print("S5L SPI patch test passed")
