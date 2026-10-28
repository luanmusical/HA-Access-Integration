"""Sensores liga/desliga do computador e o sensor "Conectado" de cada um."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ID_CONECTADO
from .entity import EntidadeHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    def criar(ap, d, plataforma):
        return ConectadoHaAccess(ap, d, plataforma) if d["id"] == ID_CONECTADO else BinarioHaAccess(ap, d, plataforma)
    await montar(hass, entry, adicionar, "binary_sensor", criar)


class ConectadoHaAccess(EntidadeHaAccess, BinarySensorEntity):
    """Ligado enquanto o programa está conectado (e mandando sinal de vida)."""
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self):
        return True

    @property
    def is_on(self):
        return self.ap.conectado


class BinarioHaAccess(EntidadeHaAccess, BinarySensorEntity, RestoreEntity):
    def __init__(self, aparelho, definicao, plataforma):
        super().__init__(aparelho, definicao, plataforma)
        try:
            self._attr_device_class = BinarySensorDeviceClass(definicao["device_class"]) \
                if definicao.get("device_class") else None
        except ValueError:
            self._attr_device_class = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # último valor conhecido (depois de reiniciar o HA), até o computador mandar um novo
        if self.ident not in self.ap.valores:
            ultimo = await self.async_get_last_state()
            if ultimo is not None and ultimo.state in ("on", "off"):
                self.ap.valores[self.ident] = {"estado": ultimo.state, "atributos": None}

    @property
    def is_on(self):
        v = (self.ap.valores.get(self.ident) or {}).get("estado")
        if v is None or v == "":
            return None
        return str(v).strip().lower() in ("on", "true", "1", "yes", "sim")

    @property
    def extra_state_attributes(self):
        a = (self.ap.valores.get(self.ident) or {}).get("atributos")
        return a if isinstance(a, dict) else None
