"""Comandos do computador como botão."""

from homeassistant.components.button import ButtonEntity

from .entity import ComandoHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "button", BotaoHaAccess)


class BotaoHaAccess(ComandoHaAccess, ButtonEntity):
    async def async_press(self):
        self._mandar("press")
