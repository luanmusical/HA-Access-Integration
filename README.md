# HA-Access — integração para o Home Assistant

[Português](#português) · [English](#english)

## Português

Esta é a integração do **HA-Access** para o Home Assistant. O HA-Access é um programa para Windows e Mac, feito para ser usado com leitor de tela (NVDA, JAWS, VoiceOver), que controla a casa pelo teclado e faz do computador um aparelho do Home Assistant, como o app do celular faz com o telefone.

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

Precisa do Home Assistant 2025.1 ou mais novo. Os ícones próprios aparecem a partir do 2026.3.

A integração está na lista oficial da **Marketplace** do Home Assistant 2026.11 (antes, HACS). Não precisa adicionar repositório personalizado.

[![Abrir no Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=luanmusical&repository=HA-Access-Integration&category=integration)

1. Abra a Marketplace (ou o HACS, nas versões antigas do Home Assistant) e procure por "HA-Access".
2. Baixe "HA-Access" e reinicie o Home Assistant.
3. Configurações, Dispositivos e serviços, Adicionar integração, HA-Access. Não tem nenhuma pergunta.

As atualizações aparecem sozinhas em Configurações, como as do próprio Home Assistant.

O programa HA-Access também faz esses passos sozinho, na janela "Conectar ao Home Assistant".

**Instalação manual:** copie a pasta `custom_components/ha_access` para a pasta `config/custom_components/` do Home Assistant e reinicie.

### Opções

Em Configurações, Dispositivos e serviços, HA-Access, Configurar:

- **Só o dono do computador e administradores controlam:** desligada por padrão. Ligada, os botões, interruptores, player e a ação `enviar_texto` de cada computador só obedecem a quem o cadastrou e aos administradores.

### Segurança e privacidade

- **Tudo local.** Nada passa por servidores de terceiros.
- **Cada computador fica preso ao usuário do Home Assistant que o cadastrou.** Outro usuário comum não consegue se passar por ele; administradores podem tudo.
- **Computador desconhecido não manda nada.** Só a conexão (`ha_access/conectar`) apresenta um computador novo. Etiqueta NFC, botão de notificação, estados, mídia e sinal de vida são recusados para um computador que a integração não conhece ou que é de outro usuário.
- **Notificações não se misturam.** Se dois usuários derem o mesmo nome aos seus computadores, cada um continua com o seu `notify.ha_access_<nome>`: o segundo ganha um final com o começo do serial.
- **Tudo o que chega do programa tem tamanho e formato conferidos**, e um usuário comum apresenta no máximo 20 computadores.
- **Versões combinadas.** O programa e a integração conferem a versão ao conectar. Se uma estiver velha demais, aparece um aviso em Reparos dizendo o que atualizar. Também aparece um aviso quando um computador usa uma versão do programa mais antiga que a recomendada.

### Licença

MIT. Luan Richard / L-R Productions.

## English

This is the **HA-Access** integration for Home Assistant. HA-Access is a Windows and Mac program built for screen reader users (NVDA, JAWS, VoiceOver). It controls the house from the keyboard and turns the computer into a Home Assistant device, the way the companion app does for a phone.

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

Requires Home Assistant 2025.1 or later. The integration's own icons need 2026.3 or later.

The integration is in the default list of the Home Assistant 2026.11 **Marketplace** (formerly HACS). No custom repository is needed.

[![Open in Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=luanmusical&repository=HA-Access-Integration&category=integration)

1. Open the Marketplace (or HACS on older Home Assistant versions) and search for "HA-Access".
2. Download "HA-Access" and restart Home Assistant.
3. Add the HA-Access integration. It asks no questions.

Updates show up in Settings like any other Home Assistant update.

### Options

Settings, Devices & services, HA-Access, Configure:

- **Only the computer's owner and administrators can control it:** off by default. When on, each computer's buttons, switches, media player and the `enviar_texto` action only obey the user who registered it and administrators.

The HA-Access program can do these steps for you.

### Security

- Everything stays local.
- Each computer is bound to the Home Assistant user that registered it; admins can do anything.
- Unknown computers cannot send anything. Only `ha_access/conectar` introduces a new computer; tag scans, notification actions, states, media and heartbeats are refused for a computer the integration does not know or that belongs to another user.
- Notification targets never collide across users: if two users give their computers the same name, the second one gets a suffix taken from its serial.
- Every message from the program is size- and format-checked, and a non-admin user can register at most 20 computers.
- The program and the integration check each other's protocol version and raise a Repairs issue when one of them must be updated. A Repairs issue also appears when a computer runs a program version older than the recommended one.

### License

MIT. Luan Richard / L-R Productions.
