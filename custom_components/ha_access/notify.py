"""Notificações, nos dois formatos do Home Assistant:

- o antigo (serviço notify.ha_access_<computador>), que aceita data (botões "actions",
  respostas "inputs", imagem, duração...), igual ao HASS.Agent e ao app do celular;
- o novo (entidade notify.<computador>_notificacao, ação notify.send_message), só mensagem e
  título: para quando o formato antigo for aposentado."""

from __future__ import annotations

from homeassistant.components.notify import (ATTR_DATA, ATTR_TARGET, ATTR_TITLE, BaseNotificationService,
                                             NotifyEntity, NotifyEntityFeature)
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import EntidadeHaAccess, montar


async def async_setup_entry(hass, entry, adicionar):
    await montar(hass, entry, adicionar, "notify", NotificacaoHaAccess)


class NotificacaoHaAccess(EntidadeHaAccess, NotifyEntity):
    _attr_supported_features = NotifyEntityFeature.TITLE

    async def async_send_message(self, message, title=None):
        dados = {"message": message, "title": title or "", "data": {}}
        if not self.ap.mandar({"tipo": "notificacao", "dados": dados}):
            raise HomeAssistantError(f"{self.ap.nome} está desconectado")


async def async_get_service(hass, config, discovery_info=None):
    hub = hass.data.get(DOMAIN)
    if hub is None:
        return None
    servico = ServicoNotificacao(hass)
    hub.notify = servico
    return servico


class ServicoNotificacao(BaseNotificationService):
    def __init__(self, hass):
        self._hass = hass

    @property
    def _hub(self):
        return self._hass.data.get(DOMAIN)

    @property
    def targets(self):
        hub = self._hub
        if hub is None:
            return {}
        return {ap.alvo_notify: serial for serial, ap in hub.aparelhos.items() if ap.info.get("notificacoes", True)}

    async def async_send_message(self, message="", **kwargs):
        hub = self._hub
        if hub is None:
            raise HomeAssistantError("A integração HA-Access não está carregada")
        alvos = kwargs.get(ATTR_TARGET) or list(self.targets.values())
        dados = {"message": message, "title": kwargs.get(ATTR_TITLE) or "", "data": kwargs.get(ATTR_DATA) or {}}
        fora = []
        for serial in alvos:
            ap = hub.aparelhos.get(serial)
            if ap is None or not ap.mandar({"tipo": "notificacao", "dados": dados}):
                fora.append(ap.nome if ap else serial)
        if fora and len(fora) == len(alvos):
            raise HomeAssistantError("Computador desconectado: " + ", ".join(fora))
