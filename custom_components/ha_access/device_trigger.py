"""Gatilho de aparelho no editor de automações: "quando um botão da notificação deste
computador for apertado" (com o nome da ação opcional), em vez do evento cru."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as gatilho_evento
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE

from .const import DOMAIN, EVENTO_ACAO

TIPO = "acao_notificacao"
CONF_ACAO = "acao"

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({
    vol.Required(CONF_TYPE): vol.In([TIPO]),
    vol.Optional(CONF_ACAO): str,
})


async def async_get_triggers(hass, device_id):
    return [{CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id, CONF_TYPE: TIPO}]


async def async_get_trigger_capabilities(hass, config):
    return {"extra_fields": vol.Schema({vol.Optional(CONF_ACAO): str})}


async def async_attach_trigger(hass, config, action, trigger_info):
    dados = {"device_id": config[CONF_DEVICE_ID]}
    if config.get(CONF_ACAO):
        dados["action"] = config[CONF_ACAO]
    evento = gatilho_evento.TRIGGER_SCHEMA({
        gatilho_evento.CONF_PLATFORM: "event",
        gatilho_evento.CONF_EVENT_TYPE: EVENTO_ACAO,
        gatilho_evento.CONF_EVENT_DATA: dados,
    })
    return await gatilho_evento.async_attach_trigger(hass, evento, action, trigger_info, platform_type="device")
