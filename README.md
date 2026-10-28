# HA-Access — integração para o Home Assistant

[Português](#português) · [English](#english)

## Português

Esta é a integração do **HA-Access** para o Home Assistant. O HA-Access é um programa para Windows, feito para ser usado com leitor de tela (NVDA, JAWS), que controla a casa pelo teclado e faz do computador um aparelho do Home Assistant, como o app do celular faz com o telefone.

A integração é a ponte: com ela o computador aparece no Home Assistant com os seus sensores, comandos, player de mídia e notificações. **Não precisa de MQTT**, nem de porta aberta no computador. Tudo passa pela conexão normal do Home Assistant, então funciona em casa e também pelo endereço externo (Nabu Casa, túnel da Cloudflare etc.).

O programa HA-Access fica em [luanmusical/HA-Access](https://github.com/luanmusical/HA-Access).

### O que aparece no Home Assistant

Para cada computador com o HA-Access conectado:

- **Sensores** escolhidos no programa: computador bloqueado, microfone e câmera em uso, janela ativa, volume, processador, memória, bateria e outros.
- **Comandos** como botões ou interruptores: bloquear, desligar a tela, suspender, reiniciar, desligar, abrir programas, teclas e outros. Também existe a ação `ha_access.enviar_texto`, para comandos que recebem um texto.
- **Player de mídia**: o que toca no computador, com volume, faixa e capa.
- **Notificações**:
  - formato antigo `notify.ha_access_<computador>`, com botões (`data.actions`), respostas (`data.inputs`), imagem e duração, igual ao app do celular;
  - entidade nova `notify.<computador>_notificacao`, para a ação `notify.send_message`.
- **Botão da notificação apertado**:
  - gatilho de aparelho no editor de automações;
  - evento `ha_access_notification_action`, com `device_id`, `action`, `input` e `uri`.
- **Sensor "Conectado"** de cada computador. Sem sinal de vida por 75 segundos, o computador fica indisponível.
- **Etiquetas NFC** lidas no computador viram "etiqueta escaneada" do Home Assistant.
- **Diagnóstico para baixar**, sem token nem dados pessoais.

### Instalação

Precisa do Home Assistant 2024.10 ou mais novo. Os ícones próprios aparecem a partir do 2026.3.

**Pelo HACS:**

1. HACS, menu, Repositórios personalizados.
2. Endereço `https://github.com/luanmusical/HA-Access-Integration`, tipo Integração.
3. Baixe "HA-Access" e reinicie o Home Assistant.
4. Configurações, Dispositivos e serviços, Adicionar integração, HA-Access. Não tem nenhuma pergunta.

O programa HA-Access também faz esses passos sozinho, na janela "Conectar ao Home Assistant".

**Instalação manual:** copie a pasta `custom_components/ha_access` para a pasta `config/custom_components/` do Home Assistant e reinicie.

### Segurança e privacidade

- **Tudo local.** Nada passa por servidores de terceiros.
- **Cada computador fica preso ao usuário do Home Assistant que o cadastrou.** Outro usuário comum não consegue se passar por ele; administradores podem tudo.
- **Versões combinadas.** O programa e a integração conferem a versão ao conectar. Se uma estiver velha demais, aparece um aviso em Reparos dizendo o que atualizar.

### Licença

MIT. Luan Richard / L-R Productions.

## English

This is the **HA-Access** integration for Home Assistant. HA-Access is a Windows program built for screen reader users (NVDA, JAWS). It controls the house from the keyboard and turns the computer into a Home Assistant device, the way the companion app does for a phone.

The integration is the bridge. It exposes the computer's sensors, commands, media player and notifications. **No MQTT is needed**, and no port has to be opened on the computer. Everything goes through the regular Home Assistant connection, so it also works through an external URL (Nabu Casa, Cloudflare tunnel...).

The HA-Access program lives at [luanmusical/HA-Access](https://github.com/luanmusical/HA-Access).

### What you get

For each connected computer:

- Sensors chosen in the program.
- Commands as buttons or switches, plus the `ha_access.enviar_texto` action.
- A media player for what is playing on the computer.
- Notifications:
  - legacy `notify.ha_access_<computer>`, with actions, inputs and image, like the companion app;
  - the new `notify.<computer>_notificacao` entity, for `notify.send_message`.
- A device trigger for pressed notification buttons, and the `ha_access_notification_action` event.
- A "Connected" sensor. The computer becomes unavailable after 75 seconds without a heartbeat.
- NFC tags scanned on the computer become Home Assistant tag scans.
- Downloadable diagnostics.

### Installation

Requires Home Assistant 2024.10 or later. The integration's own icons need 2026.3 or later.

1. In HACS, add `https://github.com/luanmusical/HA-Access-Integration` as a custom repository of type Integration.
2. Download "HA-Access" and restart Home Assistant.
3. Add the HA-Access integration. It asks no questions.

The HA-Access program can do these steps for you.

### Security

- Everything stays local.
- Each computer is bound to the Home Assistant user that registered it; admins can do anything.
- The program and the integration check each other's protocol version and raise a Repairs issue when one of them must be updated.

### License

MIT. Luan Richard / L-R Productions.
