"""Cadastro da integração: uma só, sem perguntas. Cada computador com o
HA-Access vira um aparelho dentro dela quando se conecta.

Opções (Configurar): "só o dono controla" - comandos, player e texto de um computador só para
quem o apresentou (o dono) e para administradores. Desligada por padrão: numa casa onde todos
usam os computadores uns dos outros, nada muda."""

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback

from .const import DOMAIN, OPCAO_SO_DONO


class HaAccessFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="HA-Access", data={})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OpcoesHaAccess()


class OpcoesHaAccess(OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        atual = self.config_entry.options.get(OPCAO_SO_DONO, False)
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Optional(OPCAO_SO_DONO, default=atual): bool}))
