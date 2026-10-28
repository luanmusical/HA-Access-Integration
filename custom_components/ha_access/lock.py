"""Comandos do computador como fechadura (trancar = ligar)."""

from homeassistant.components.lock import LockEntity

from .entity import ComandoHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "lock", TravaHaAccess)


class TravaHaAccess(ComandoHaAccess, LockEntity):
    @property
    def is_locked(self):
        return self.ligado

    async def async_lock(self, **kwargs):
        self._mandar("lock")

    async def async_unlock(self, **kwargs):
        self._mandar("unlock")
