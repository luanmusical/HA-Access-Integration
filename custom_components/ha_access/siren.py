"""Comandos do computador como sirene."""

from homeassistant.components.siren import SirenEntity, SirenEntityFeature

from .entity import ComandoHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "siren", SireneHaAccess)


class SireneHaAccess(ComandoHaAccess, SirenEntity):
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    @property
    def is_on(self):
        return self.ligado

    async def async_turn_on(self, **kwargs):
        self._mandar("on")

    async def async_turn_off(self, **kwargs):
        self._mandar("off")
