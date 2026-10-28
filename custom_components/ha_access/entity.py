"""Base das entidades e montagem das plataformas."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, PLATAFORMAS_COMANDO
from .hub import sinal_novas


async def montar(hass, entry, adicionar, plataforma, classe):
    """Cria as entidades conhecidas e as que chegarem quando um computador conectar."""
    hub = entry.runtime_data
    adicionar([classe(ap, d, plataforma) for ap, d in hub.definicoes(plataforma)])
    @callback          # sem isto o HA roda numa thread à parte e recusa criar as entidades
    def novas(itens):
        adicionar([classe(ap, d, plataforma) for ap, d in itens])

    entry.async_on_unload(async_dispatcher_connect(hass, sinal_novas(plataforma), novas))
    if plataforma in PLATAFORMAS_COMANDO:
        entity_platform.async_get_current_platform().async_register_entity_service(
            "enviar_texto", {vol.Required("texto"): str}, "async_enviar_texto")


class EntidadeHaAccess(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, aparelho, definicao, plataforma):
        self.ap = aparelho
        self.d = definicao
        self.plataforma = plataforma
        self.ident = definicao["id"]
        self._attr_unique_id = f"{aparelho.serial}_{self.ident}"
        self._attr_name = definicao.get("nome")
        if definicao.get("icone"):
            self._attr_icon = definicao["icone"]
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, aparelho.serial)})

    @property
    def available(self):
        return self.ap.conectado or bool(self.d.get("sempre_disponivel"))

    async def async_added_to_hass(self):
        self.ap.entidades[(self.plataforma, self.ident)] = self

    async def async_will_remove_from_hass(self):
        if self.ap.entidades.get((self.plataforma, self.ident)) is self:
            self.ap.entidades.pop((self.plataforma, self.ident), None)


class ComandoHaAccess(EntidadeHaAccess):
    """Comando do computador: o HA manda, o programa executa e devolve o estado."""

    @property
    def ligado(self):
        return self.ap.comandos_ligados.get(self.ident)

    def _mandar(self, acao, texto=None):
        dados = {"tipo": "comando", "id": self.ident, "acao": acao}
        if texto is not None:
            dados["texto"] = texto
        if not self.ap.mandar(dados):
            raise HomeAssistantError(f"{self.ap.nome} está desconectado")

    async def async_enviar_texto(self, texto):
        self._mandar("texto", texto)
