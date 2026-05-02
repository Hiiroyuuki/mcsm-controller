# Minecraft Java Edition Common Commands for OpenClaw

This file is optimized for **fast retrieval by OpenClaw**.

## Retrieval Rules

- Scope: **Minecraft Java Edition only**
- Console form: **do not include a leading slash** in `MCSManager` console
- In-game form: same command but usually written with `/`
- Canonical field order in tables:
  - `command`
  - `aliases`
  - `category`
  - `purpose`
  - `first_version`
  - `last_version`
  - `status`
  - `source`
- `last_version = 26.1.2` means the command is still available and was confirmed against Mojang's official `Java Edition 26.1.2` release page dated `2026-04-09`
- If a command was removed, `status = removed` and `last_version` is the last known Java version from Minecraft Wiki history

## Version Sources

- Mojang latest confirmation page: <https://www.minecraft.net/en-us/article/minecraft-java-edition-26-1-2>
- Minecraft Wiki command index: <https://minecraft.wiki/w/Commands>

## Quick Intent Index

| intent | commands |
| --- | --- |
| announce to all players | `say`, `tellraw`, `title` |
| private message | `msg`, `tell`, `w` |
| player movement | `tp`, `teleport`, `spawnpoint` |
| world time and weather | `time`, `weather` |
| player mode and rules | `gamemode`, `defaultgamemode`, `difficulty`, `gamerule` |
| inventory and items | `give`, `clear`, `item`, `enchant`, `experience`, `xp` |
| entity and effects | `summon`, `kill`, `effect`, `tag`, `execute`, `data` |
| block editing | `setblock`, `fill`, `clone` |
| automation | `function`, `schedule`, `scoreboard`, `reload`, `datapack` |
| locate and border | `locate`, `worldborder` |
| save and shutdown | `save-all`, `save-off`, `save-on`, `stop` |
| moderation | `kick`, `ban`, `ban-ip`, `pardon`, `pardon-ip`, `whitelist`, `op`, `deop` |

## Active Common Commands

| command | aliases | category | purpose | first_version | last_version | status | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [`help`](https://minecraft.wiki/w/Commands/help) | none | chat-admin | show command help | early dedicated server era; singleplayer cheats from `1.3.1` | `26.1.2` | active | Wiki + Mojang |
| [`list`](https://minecraft.wiki/w/Commands/list) | none | server-admin | list online players | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`say`](https://minecraft.wiki/w/Commands/say) | none | chat | broadcast plain text to all players | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`msg`](https://minecraft.wiki/w/Commands/msg) | `tell`, `w` | chat | private message to target player | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`tellraw`](https://minecraft.wiki/w/Commands/tellraw) | none | chat-ui | send JSON rich-text message | `1.7.2` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`title`](https://minecraft.wiki/w/Commands/title) | none | chat-ui | show title or action-bar text | `1.8` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`gamemode`](https://minecraft.wiki/w/Commands/gamemode) | none | player-state | set player game mode | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`defaultgamemode`](https://minecraft.wiki/w/Commands/defaultgamemode) | none | player-state | set default game mode for joining players | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`difficulty`](https://minecraft.wiki/w/Commands/difficulty) | none | player-state | set world difficulty | early dedicated server era; singleplayer cheats from `1.3.1` | `26.1.2` | active | Wiki + Mojang |
| [`gamerule`](https://minecraft.wiki/w/Commands/gamerule) | none | player-state | change rules such as `keepInventory` | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`give`](https://minecraft.wiki/w/Commands/give) | none | inventory | give items to player | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`clear`](https://minecraft.wiki/w/Commands/clear) | none | inventory | clear matching items from inventory | `1.4.2` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`item`](https://minecraft.wiki/w/Commands/item) | none | inventory | replace or modify slot items in entities or containers | `1.17` `20w46a` | `26.1.2` | active | Wiki + Mojang |
| [`enchant`](https://minecraft.wiki/w/Commands/enchant) | none | inventory | enchant held item | around `1.4.4` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`experience`](https://minecraft.wiki/w/Commands/experience) | `xp` | player-state | add or remove XP points or levels | `/xp` older; `/experience` standardized in `1.13` | `26.1.2` | active | Wiki + Mojang |
| [`effect`](https://minecraft.wiki/w/Commands/effect) | none | player-state | add or remove status effects | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`kill`](https://minecraft.wiki/w/Commands/kill) | none | entity | instantly kill target entity or player | around `1.4.2` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`teleport`](https://minecraft.wiki/w/Commands/teleport) | `tp` | movement | teleport entities | `/tp` very old; `/teleport` added in `1.11` `16w39a` | `26.1.2` | active | Wiki + Mojang |
| [`spawnpoint`](https://minecraft.wiki/w/Commands/spawnpoint) | none | movement | set personal respawn point | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`time`](https://minecraft.wiki/w/Commands/time) | none | world | set or query world time | early dedicated server era; singleplayer cheats from `1.3.1` | `26.1.2` | active | Wiki + Mojang |
| [`weather`](https://minecraft.wiki/w/Commands/weather) | none | world | set clear, rain, or thunder | around `1.3.1` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`setworldspawn`](https://minecraft.wiki/w/Commands/setworldspawn) | none | world | set default world spawn | around `1.4.2` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`summon`](https://minecraft.wiki/w/Commands/summon) | none | entity | summon entity with optional NBT | `1.4.2` `12w32a` | `26.1.2` | active | Wiki + Mojang |
| [`tag`](https://minecraft.wiki/w/Commands/tag) | none | entity | add or remove entity tags | `1.9` `15w31a` | `26.1.2` | active | Wiki + Mojang |
| [`execute`](https://minecraft.wiki/w/Commands/execute) | none | entity-automation | conditional or contextual command execution | took shape in `1.8` `13w03a`; major rewrite in `1.13` | `26.1.2` | active | Wiki + Mojang |
| [`data`](https://minecraft.wiki/w/Commands/data) | none | entity-automation | read or modify NBT/data on entities, blocks, or storage | `1.13` `17w45b` | `26.1.2` | active | Wiki + Mojang |
| [`setblock`](https://minecraft.wiki/w/Commands/setblock) | none | block-edit | set one block | `1.8` `14w03a` | `26.1.2` | active | Wiki + Mojang |
| [`fill`](https://minecraft.wiki/w/Commands/fill) | none | block-edit | fill a region with blocks | `1.8` `14w03a` | `26.1.2` | active | Wiki + Mojang |
| [`clone`](https://minecraft.wiki/w/Commands/clone) | none | block-edit | copy a block region | `1.8` `14w03a` | `26.1.2` | active | Wiki + Mojang |
| [`particle`](https://minecraft.wiki/w/Commands/particle) | none | world-ui | spawn particles | `1.8` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`playsound`](https://minecraft.wiki/w/Commands/playsound) | none | world-ui | play a sound to players | `1.7.2` / `1.7.4` snapshot era | `26.1.2` | active | Wiki + Mojang |
| [`locate`](https://minecraft.wiki/w/Commands/locate) | none | world-query | find structures, biomes, or POIs | `1.11` `16w39a`; unified subcommands from `1.19` | `26.1.2` | active | Wiki + Mojang |
| [`worldborder`](https://minecraft.wiki/w/Commands/worldborder) | none | world-admin | configure world border | `1.8` `14w17a` | `26.1.2` | active | Wiki + Mojang |
| [`scoreboard`](https://minecraft.wiki/w/Commands/scoreboard) | none | automation | manage objectives, scores, and HUD logic | `1.5` `13w04a` | `26.1.2` | active | Wiki + Mojang |
| [`function`](https://minecraft.wiki/w/Commands/function) | none | automation | run a data-pack function | `1.12` `pre1` | `26.1.2` | active | Wiki + Mojang |
| [`schedule`](https://minecraft.wiki/w/Commands/schedule) | none | automation | delay function execution | `1.15` `19w38a` | `26.1.2` | active | Wiki + Mojang |
| [`reload`](https://minecraft.wiki/w/Commands/reload) | none | automation | reload data packs and related content | `1.12` `17w18a` | `26.1.2` | active | Wiki + Mojang |
| [`datapack`](https://minecraft.wiki/w/Commands/datapack) | none | automation | enable, disable, or reorder data packs | after `1.13` command rewrite | `26.1.2` | active | Wiki + Mojang |
| [`save-all`](https://minecraft.wiki/w/Commands/save-all) | none | server-admin | save all chunks and player data now | Alpha / early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`save-off`](https://minecraft.wiki/w/Commands/save-off) | none | server-admin | disable automatic saving | Alpha / early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`save-on`](https://minecraft.wiki/w/Commands/save-on) | none | server-admin | re-enable automatic saving | Alpha / early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`stop`](https://minecraft.wiki/w/Commands/stop) | none | server-admin | safely shut down server | Alpha / early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`seed`](https://minecraft.wiki/w/Commands/seed) | none | server-query | show world seed | `1.3.1` singleplayer-cheat era; long supported on servers | `26.1.2` | active | Wiki + Mojang |
| [`setidletimeout`](https://minecraft.wiki/w/Commands/setidletimeout) | none | server-admin | set AFK timeout | around `1.7` era | `26.1.2` | active | Wiki + Mojang |
| [`kick`](https://minecraft.wiki/w/Commands/kick) | none | moderation | kick player from server | Classic `0.0.16a` | `26.1.2` | active | Wiki + Mojang |
| [`ban`](https://minecraft.wiki/w/Commands/ban) | none | moderation | ban player by name | Classic `0.0.16a`; re-added in Alpha `v1.0.16` | `26.1.2` | active | Wiki + Mojang |
| [`ban-ip`](https://minecraft.wiki/w/Commands/ban-ip) | `banip` legacy spelling | moderation | ban by IP address | from Classic `0.0.16a` `/banip`; modern form normalized later | `26.1.2` | active | Wiki + Mojang |
| [`pardon`](https://minecraft.wiki/w/Commands/pardon) | none | moderation | unban player by name | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`pardon-ip`](https://minecraft.wiki/w/Commands/pardon-ip) | none | moderation | unban IP address | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`whitelist`](https://minecraft.wiki/w/Commands/whitelist) | none | moderation | manage whitelist | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`op`](https://minecraft.wiki/w/Commands/op) | none | moderation | grant operator privileges | early dedicated server era | `26.1.2` | active | Wiki + Mojang |
| [`deop`](https://minecraft.wiki/w/Commands/deop) | none | moderation | remove operator privileges | early dedicated server era | `26.1.2` | active | Wiki + Mojang |

## Common Java `gamerule` Rules

- Command syntax: `gamerule <rule> [value]`
- Query current value: `gamerule keepInventory`
- Set boolean value: `gamerule keepInventory true`
- Set integer value: `gamerule randomTickSpeed 3`
- Java note: rule names are **case-sensitive**

| rule | type | default | purpose | added_in | last_version | example | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `keepInventory` | bool | `false` | keep items and XP after death | `1.4.2` `12w32a` | `26.1.2` | `gamerule keepInventory true` | Wiki + Mojang |
| `doDaylightCycle` | bool | `true` | stop or resume the day-night cycle | `1.6.1` `13w24a` | `26.1.2` | `gamerule doDaylightCycle false` | Wiki + Mojang |
| `doWeatherCycle` | bool | `true` | stop or resume natural weather changes | `1.11` `16w38a` | `26.1.2` | `gamerule doWeatherCycle false` | Wiki + Mojang |
| `mobGriefing` | bool | `true` | control whether mobs can modify blocks or pick up some items | `1.4.2` `12w32a` | `26.1.2` | `gamerule mobGriefing false` | Wiki + Mojang |
| `doMobSpawning` | bool | `true` | control natural mob spawning | `1.4.2` `12w32a` | `26.1.2` | `gamerule doMobSpawning false` | Wiki + Mojang |
| `naturalRegeneration` | bool | `true` | control hunger-based health regeneration | `1.6.1` `13w23a` | `26.1.2` | `gamerule naturalRegeneration false` | Wiki + Mojang |
| `randomTickSpeed` | int | `3` | control crop growth, leaf decay, and many random block updates | `1.8` `14w17a` | `26.1.2` | `gamerule randomTickSpeed 0` | Wiki + Mojang |
| `sendCommandFeedback` | bool | `true` | control whether command feedback appears in chat/output | `1.8` `14w26a` | `26.1.2` | `gamerule sendCommandFeedback false` | Wiki + Mojang |
| `commandBlockOutput` | bool | `true` | control whether command blocks notify admins | `1.4.2` `12w38a` | `26.1.2` | `gamerule commandBlockOutput false` | Wiki + Mojang |
| `showDeathMessages` | bool | `true` | control death messages in chat | `1.8` `14w10a` | `26.1.2` | `gamerule showDeathMessages false` | Wiki + Mojang |
| `doImmediateRespawn` | bool | `false` | make players respawn without the death screen | `1.15` `19w36a` | `26.1.2` | `gamerule doImmediateRespawn true` | Wiki + Mojang |
| `playersSleepingPercentage` | int | `100` | control what percent of players must sleep to skip night | `1.17` `20w51a` | `26.1.2` | `gamerule playersSleepingPercentage 1` | Wiki + Mojang |
| `doInsomnia` | bool | `true` | control phantom spawning from lack of sleep | `1.15` `19w36a` | `26.1.2` | `gamerule doInsomnia false` | Wiki + Mojang |
| `doPatrolSpawning` | bool | `true` | control patrol spawning | `1.15.2` `pre1` | `26.1.2` | `gamerule doPatrolSpawning false` | Wiki + Mojang |
| `doTraderSpawning` | bool | `true` | control wandering trader spawning | `1.15.2` `pre1` | `26.1.2` | `gamerule doTraderSpawning false` | Wiki + Mojang |
| `universalAnger` | bool | `false` | make angered neutral mobs target any nearby player | `1.16` `pre1` | `26.1.2` | `gamerule universalAnger true` | Wiki + Mojang |
| `forgiveDeadPlayers` | bool | `true` | make neutral mobs stop being angry after the target player dies | `1.16` `pre1` | `26.1.2` | `gamerule forgiveDeadPlayers false` | Wiki + Mojang |
| `doWardenSpawning` | bool | `true` | control warden spawning | `1.19` `22w16a` | `26.1.2` | `gamerule doWardenSpawning false` | Wiki + Mojang |

## `gamerule` Preset Intents

| intent | recommended command |
| --- | --- |
| keep inventory on death | `gamerule keepInventory true` |
| freeze time at current moment | `gamerule doDaylightCycle false` |
| freeze weather | `gamerule doWeatherCycle false` |
| disable creeper and enderman griefing | `gamerule mobGriefing false` |
| stop natural mob spawning | `gamerule doMobSpawning false` |
| disable natural healing | `gamerule naturalRegeneration false` |
| disable phantoms | `gamerule doInsomnia false` |
| skip night with one sleeper | `gamerule playersSleepingPercentage 1` |
| silence command spam | `gamerule sendCommandFeedback false` |
| hide command block output | `gamerule commandBlockOutput false` |
| immediate respawn | `gamerule doImmediateRespawn true` |

## Removed or Replaced Java Commands

| command | aliases | category | purpose | first_version | last_version | status | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [`achievement`](https://minecraft.wiki/w/Commands/achievement) | none | removed | old achievement grant command; replaced by `advancement` | old achievement-system era | `1.11.2` | removed | Wiki |
| [`placefeature`](https://minecraft.wiki/w/Commands/placefeature) | none | removed | old feature placement command; merged into `place feature` | `1.18.2` `22w03a` | `1.19` `22w18a` | removed | Wiki |
| `locatebiome` | none | removed | old biome lookup command; merged into `locate biome` | `1.18` era | `1.19` `22w19a` | removed | Wiki |
| `banip` | replaced by `ban-ip` | removed-alias | legacy spelling for IP ban | Classic `0.0.16a` | before/at `1.13` normalization | removed-alias | Wiki |
| `scoreboard teams` | replaced by `team` | removed-pattern | old team-management pattern within `scoreboard` | old scoreboard era | superseded in modern versions | superseded | Wiki |

## OpenClaw Extraction Hints

- Prefer `command` over aliases when generating instructions.
- If a user asks for a private-message command, normalize to `msg`.
- If a user asks for teleport, normalize to `teleport`, but accept `tp`.
- If a user asks whether a command still exists:
  - `status = active` means usable in Java Edition as of `26.1.2`
  - `status = removed` means do not use it on modern Java servers
- If a user asks for a gameplay rule change, prefer:
  - `gamerule keepInventory true`
  - `gamerule doDaylightCycle false`
  - `gamerule doWeatherCycle false`
  - `gamerule mobGriefing false`
  - `gamerule sendCommandFeedback false`
- For `mcsm-controller` console output, emit commands like:
  - `say hello`
  - `tp Steve 0 80 0`
  - `weather clear`
  - `gamerule keepInventory true`
  - `save-all`
  - `stop`
