"""Sensores do computador (valores lidos pelo programa)."""

from __future__ import annotations

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.util import dt as dt_util

from .entity import EntidadeHaAccess, montar

_TEXTO_MAX = 255


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "sensor", SensorHaAccess)


class SensorHaAccess(EntidadeHaAccess, RestoreSensor):
    def __init__(self, aparelho, definicao, plataforma):
        super().__init__(aparelho, definicao, plataforma)
        self._attr_native_unit_of_measurement = definicao.get("unidade") or None
        try:
            self._attr_device_class = SensorDeviceClass(definicao["device_class"]) \
                if definicao.get("device_class") else None
        except ValueError:
            self._attr_device_class = None
        try:
            self._attr_state_class = SensorStateClass(definicao["state_class"]) \
                if definicao.get("state_class") else None
        except ValueError:
            self._attr_state_class = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # último valor conhecido (depois de reiniciar o HA), até o computador mandar um novo
        if self.ident not in self.ap.valores:
            ultimo = await self.async_get_last_sensor_data()
            if ultimo is not None and ultimo.native_value is not None:
                self.ap.valores[self.ident] = {"estado": str(ultimo.native_value), "atributos": None}

    @property
    def native_value(self):
        v = (self.ap.valores.get(self.ident) or {}).get("estado")
        if v is None or v == "":
            return None
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            d = dt_util.parse_datetime(str(v))
            if d is not None and d.tzinfo is None:
                d = d.replace(tzinfo=dt_util.get_default_time_zone())
            return d
        if self._attr_native_unit_of_measurement or self._attr_state_class or (
                self._attr_device_class not in (None, SensorDeviceClass.ENUM, SensorDeviceClass.DATE)):
            try:
                return float(str(v).replace(",", "."))
            except ValueError:
                return None
        return str(v)[:_TEXTO_MAX]

    @property
    def extra_state_attributes(self):
        a = (self.ap.valores.get(self.ident) or {}).get("atributos")
        if isinstance(a, dict):
            return a
        return {"valores": a} if a else None
