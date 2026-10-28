"""Comandos do computador como interruptor."""

from homeassistant.components.switch import SwitchEntity

from .entity import ComandoHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "switch", InterruptorHaAccess)


class InterruptorHaAccess(ComandoHaAccess, SwitchEntity):
    @property
    def is_on(self):
        return self.ligado

    async def async_turn_on(self, **kwargs):
        self._mandar("on")

    async def async_turn_off(self, **kwargs):
        self._mandar("off")
