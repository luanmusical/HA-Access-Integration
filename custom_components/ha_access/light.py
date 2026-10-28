"""Comandos do computador como luz (só liga e desliga)."""

from homeassistant.components.light import ColorMode, LightEntity

from .entity import ComandoHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "light", LuzHaAccess)


class LuzHaAccess(ComandoHaAccess, LightEntity):
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def is_on(self):
        return self.ligado

    async def async_turn_on(self, **kwargs):
        self._mandar("on")

    async def async_turn_off(self, **kwargs):
        self._mandar("off")
