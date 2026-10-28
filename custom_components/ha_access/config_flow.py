"""Cadastro da integração: uma só, sem perguntas. Cada computador com o
HA-Access vira um aparelho dentro dela quando se conecta."""

from homeassistant.config_entries import ConfigFlow

from .const import DOMAIN


class HaAccessFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="HA-Access", data={})
