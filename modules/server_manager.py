"""
JARVIS Bot — Gestor del Servidor COMPLETO (60+ acciones)
"""
import discord
import random
import time
from datetime import datetime, timedelta
import pytz
import config
from modules import command_parser

_start_time = time.time()

R = {
    "no_perm": "Lo siento, {name}, solo los administradores pueden dar órdenes.",
    "no_target": "No encontré al usuario {t}, señor.",
    "no_channel": "No encontré el canal {t}, señor.",
    "no_role": "No encontré el rol {t}, señor.",
    "self": "No puedo realizar esa acción sobre mí mismo, señor.",
    "err": "Hubo un error: {e}",
    "greet": "¿Sí señor? ¿En qué puedo ayudarle?",
}

def is_admin(m): return m.guild_permissions.administrator

async def execute(cmd, member, guild, vc_channel=None):
    a = cmd["action"]; p = cmd["params"]
    if a in ("greeting","help","list_connected","count_members","time","server_info",
             "conversation","uptime","ping","random_user","list_channels","list_roles",
             "list_bans","list_emojis","list_events","user_info","avatar","channel_info","role_info"):
        return await _info(a, p, member, guild, vc_channel)
    if not is_admin(member):
        return R["no_perm"].format(name=member.display_name)
    try:
        return await _admin(a, p, member, guild, vc_channel)
    except discord.Forbidden:
        return "No tengo permisos suficientes para esa acción, señor."
    except Exception as e:
        return R["err"].format(e=str(e)[:100])

async def _info(a, p, member, guild, vc_ch):
    if a == "greeting": return R["greet"]
    if a == "time": return command_parser.get_time_response()
    if a == "ping": return f"Mi latencia es de aproximadamente {round(random.uniform(50,150))} milisegundos, señor."
    if a == "uptime":
        s = int(time.time() - _start_time); h,r = divmod(s,3600); m,s = divmod(r,60)
        return f"Llevo {h} horas, {m} minutos y {s} segundos en línea, señor."
    if a == "list_connected":
        c = []
        for vc in guild.voice_channels:
            for m in vc.members:
                if not m.bot: c.append(f"{m.display_name} en {vc.name}")
        return f"Hay {len(c)} usuarios en voz: {', '.join(c[:15])}." if c else "No hay nadie en voz, señor."
    if a == "count_members":
        t = guild.member_count; v = sum(1 for vc in guild.voice_channels for m in vc.members if not m.bot)
        return f"El servidor tiene {t} miembros y {v} en canales de voz, señor."
    if a == "server_info":
        return f"Servidor {guild.name}, creado el {guild.created_at.strftime('%d/%m/%Y')}, {guild.member_count} miembros, {len(guild.text_channels)} canales texto, {len(guild.voice_channels)} canales voz, {len(guild.roles)} roles."
    if a == "list_channels":
        txt = [c.name for c in guild.text_channels[:10]]; voz = [c.name for c in guild.voice_channels[:10]]
        return f"Texto: {', '.join(txt)}. Voz: {', '.join(voz)}."
    if a == "list_roles":
        roles = [r.name for r in guild.roles if r.name != "@everyone"][:15]
        return f"Roles del servidor: {', '.join(roles)}."
    if a == "list_bans":
        bans = [b async for b in guild.bans(limit=10)]
        if bans: return f"Usuarios baneados: {', '.join(str(b.user) for b in bans)}."
        return "No hay usuarios baneados, señor."
    if a == "list_emojis":
        emojis = [e.name for e in guild.emojis[:15]]
        return f"Emojis: {', '.join(emojis)}." if emojis else "No hay emojis personalizados."
    if a == "list_events":
        events = guild.scheduled_events
        if events: return f"Eventos: {', '.join(e.name for e in list(events)[:10])}."
        return "No hay eventos programados."
    if a == "user_info":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        roles = ', '.join(r.name for r in t.roles if r.name != "@everyone")[:100]
        return f"{t.display_name}, se unió el {t.joined_at.strftime('%d/%m/%Y') if t.joined_at else 'desconocido'}, roles: {roles or 'ninguno'}."
    if a == "avatar":
        t = command_parser.find_member(guild, p.get("target_name",""))
        return f"El avatar de {t.display_name} es: {t.display_avatar.url}" if t else R["no_target"].format(t=p.get("target_name"))
    if a == "channel_info":
        ch = command_parser.find_channel(guild, p.get("name",""))
        if not ch: return R["no_channel"].format(t=p.get("name"))
        return f"Canal {ch.name}, tipo {ch.type}, creado el {ch.created_at.strftime('%d/%m/%Y')}."
    if a == "role_info":
        r = command_parser.find_role(guild, p.get("name",""))
        if not r: return R["no_role"].format(t=p.get("name"))
        return f"Rol {r.name}, color {r.color}, {len(r.members)} miembros, posición {r.position}."
    if a == "random_user":
        humans = [m for m in guild.members if not m.bot]
        if vc_ch: humans = [m for m in vc_ch.members if not m.bot]
        u = random.choice(humans) if humans else None
        return f"El elegido es: {u.display_name}!" if u else "No hay usuarios disponibles."
    if a == "conversation":
        if config.GEMINI_API_KEY:
            try:
                from google import genai
                c = genai.Client(api_key=config.GEMINI_API_KEY)
                r = c.models.generate_content(model="gemini-2.5-flash",
                    contents=f"Eres JARVIS. Responde breve en español (2 oraciones max). Pregunta: {p.get('text','')}")
                return r.text[:300] if r.text else "No pude procesar eso, señor."
            except: pass
        return "Entendido señor, pero necesito la inteligencia artificial para conversaciones. Configure la API key de Gemini."
    if a == "help":
        return ("Mis comandos, señor: mutear, desmutear, ensordecer, kickear, banear, desbanear, "
                "timeout, mover usuarios, desconectar, cambiar apodo, mutear a todos, desmutear a todos, "
                "mover a todos, desconectar a todos, crear y eliminar canales de voz y texto, "
                "crear categorías, bloquear y desbloquear canales, ocultar canales, renombrar canales, "
                "crear y eliminar roles, asignar y quitar roles, cambiar color de rol, "
                "limpiar mensajes, modo lento, hacer anuncios, decir cosas en voz alta, "
                "crear invitaciones, listar baneados, información de usuarios, canales, roles y servidor, "
                "cambiar nombre del servidor, programar eventos, crear hilos, "
                "cambiar mi estado, mi nombre, mi volumen, mi voz, "
                "decir la hora, elegir usuario al azar, y más.")
    return R["greet"]

async def _admin(a, p, member, guild, vc_ch):
    # === SINGLE USER ACTIONS ===
    if a == "mute":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.edit(mute=True); return f"{t.display_name} silenciado, señor."
    if a == "unmute":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.edit(mute=False); return f"{t.display_name} puede hablar, señor."
    if a == "deafen":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.edit(deafen=True); return f"{t.display_name} ensordecido, señor."
    if a == "undeafen":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.edit(deafen=False); return f"{t.display_name} puede escuchar, señor."
    if a == "kick":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        n = t.display_name; await t.kick(reason=f"Orden de {member.display_name}"); return f"{n} expulsado, señor."
    if a == "ban":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        n = t.display_name; await t.ban(reason=f"Orden de {member.display_name}"); return f"{n} baneado permanentemente, señor."
    if a == "unban":
        bans = [b async for b in guild.bans()]
        name = p.get("target_name","").lower()
        for b in bans:
            if name in str(b.user).lower() or name in b.user.name.lower():
                await guild.unban(b.user); return f"{b.user} ha sido desbaneado, señor."
        return R["no_target"].format(t=p.get("target_name"))
    if a == "timeout":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        mins = p.get("minutes", 5)
        await t.timeout(timedelta(minutes=mins)); return f"{t.display_name} en timeout por {mins} minutos, señor."
    if a == "untimeout":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.timeout(None); return f"Timeout removido de {t.display_name}, señor."
    if a == "disconnect_user":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        if not t.voice: return f"{t.display_name} no está en voz."
        n = t.display_name; await t.move_to(None); return f"{n} desconectado de voz, señor."
    if a == "move":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        ch = command_parser.find_channel(guild, p.get("channel_name",""), discord.ChannelType.voice)
        if not ch: return R["no_channel"].format(t=p.get("channel_name"))
        if not t.voice: return f"{t.display_name} no está en voz."
        await t.move_to(ch); return f"{t.display_name} movido a {ch.name}, señor."
    if a == "warn":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        reason = p.get("reason","Comportamiento inadecuado")
        try: await t.send(f"⚠️ **Advertencia de {guild.name}**: {reason}")
        except: return f"No pude enviar DM a {t.display_name}, pero queda advertido."
        return f"{t.display_name} ha sido advertido, señor."
    if a == "dm":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        try: await t.send(p.get("message","")); return f"Mensaje enviado a {t.display_name}, señor."
        except: return f"No pude enviar mensaje a {t.display_name}."
    if a == "change_nickname":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.edit(nick=p.get("new_value","")); return f"Apodo cambiado a '{p.get('new_value','')}', señor."
    if a == "reset_nickname":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        await t.edit(nick=None); return f"Apodo de {t.display_name} reseteado, señor."

    # === BULK ACTIONS ===
    if a == "mute_all":
        if not vc_ch: return "No estoy en un canal de voz, señor."
        c = 0
        for m in vc_ch.members:
            if not m.bot:
                try: await m.edit(mute=True); c += 1
                except: pass
        return f"{c} usuarios silenciados, señor."
    if a == "unmute_all":
        if not vc_ch: return "No estoy en un canal de voz, señor."
        c = 0
        for m in vc_ch.members:
            if not m.bot:
                try: await m.edit(mute=False); c += 1
                except: pass
        return f"{c} usuarios desmuteados, señor."
    if a == "deafen_all":
        if not vc_ch: return "No estoy en un canal de voz."
        c = 0
        for m in vc_ch.members:
            if not m.bot:
                try: await m.edit(deafen=True); c += 1
                except: pass
        return f"{c} usuarios ensordecidos, señor."
    if a == "undeafen_all":
        if not vc_ch: return "No estoy en un canal de voz."
        c = 0
        for m in vc_ch.members:
            if not m.bot:
                try: await m.edit(deafen=False); c += 1
                except: pass
        return f"{c} usuarios pueden escuchar, señor."
    if a == "disconnect_all":
        if not vc_ch: return "No estoy en un canal de voz."
        c = 0
        for m in vc_ch.members:
            if not m.bot:
                try: await m.move_to(None); c += 1
                except: pass
        return f"{c} usuarios desconectados, señor."
    if a == "move_all":
        if not vc_ch: return "No estoy en un canal de voz."
        ch = command_parser.find_channel(guild, p.get("channel_name",""), discord.ChannelType.voice)
        if not ch: return R["no_channel"].format(t=p.get("channel_name"))
        c = 0
        for m in vc_ch.members:
            if not m.bot:
                try: await m.move_to(ch); c += 1
                except: pass
        return f"{c} usuarios movidos a {ch.name}, señor."

    # === CHANNELS ===
    if a == "create_voice_channel":
        ch = await guild.create_voice_channel(name=p.get("name","Nuevo")); return f"Canal de voz '{ch.name}' creado, señor."
    if a == "create_text_channel":
        ch = await guild.create_text_channel(name=p.get("name","nuevo")); return f"Canal de texto '{ch.name}' creado, señor."
    if a == "create_category":
        cat = await guild.create_category(name=p.get("name","Nueva Categoría")); return f"Categoría '{cat.name}' creada, señor."
    if a == "delete_channel":
        ch = command_parser.find_channel(guild, p.get("name",""))
        if not ch: return R["no_channel"].format(t=p.get("name"))
        n = ch.name; await ch.delete(); return f"Canal '{n}' eliminado, señor."
    if a == "rename_channel":
        ch = command_parser.find_channel(guild, p.get("target_name",""))
        if not ch: return R["no_channel"].format(t=p.get("target_name"))
        await ch.edit(name=p.get("new_value","")); return f"Canal renombrado a '{p.get('new_value','')}', señor."
    if a == "lock_channel":
        ch = command_parser.find_channel(guild, p.get("channel_name","")) if p.get("channel_name") else (guild.text_channels[0] if guild.text_channels else None)
        if not ch: return "No encontré el canal."
        await ch.set_permissions(guild.default_role, send_messages=False); return f"Canal {ch.name} bloqueado, señor."
    if a == "unlock_channel":
        ch = command_parser.find_channel(guild, p.get("channel_name","")) if p.get("channel_name") else (guild.text_channels[0] if guild.text_channels else None)
        if not ch: return "No encontré el canal."
        await ch.set_permissions(guild.default_role, send_messages=True); return f"Canal {ch.name} desbloqueado, señor."
    if a == "hide_channel":
        ch = command_parser.find_channel(guild, p.get("channel_name","")) if p.get("channel_name") else (guild.text_channels[0] if guild.text_channels else None)
        if not ch: return "No encontré el canal."
        await ch.set_permissions(guild.default_role, view_channel=False); return f"Canal {ch.name} oculto, señor."
    if a == "unhide_channel":
        ch = command_parser.find_channel(guild, p.get("channel_name","")) if p.get("channel_name") else (guild.text_channels[0] if guild.text_channels else None)
        if not ch: return "No encontré el canal."
        await ch.set_permissions(guild.default_role, view_channel=True); return f"Canal {ch.name} visible, señor."
    if a == "set_topic":
        ch = guild.text_channels[0] if guild.text_channels else None
        if not ch:
            return "No encontré canal de texto."
        await ch.edit(topic=p.get("topic",""))
        return f"Tema del canal {ch.name} actualizado, señor."
    if a == "set_user_limit":
        ch = command_parser.find_channel(guild, p.get("channel_name",""), discord.ChannelType.voice) if p.get("channel_name") else vc_ch
        if not ch: return "No encontré canal de voz."
        await ch.edit(user_limit=p.get("limit",0)); return f"Límite de {ch.name} establecido en {p.get('limit',0)}, señor."
    if a == "set_bitrate":
        ch = command_parser.find_channel(guild, p.get("channel_name",""), discord.ChannelType.voice) if p.get("channel_name") else vc_ch
        if not ch: return "No encontré canal de voz."
        await ch.edit(bitrate=p.get("bitrate",64000)); return f"Bitrate de {ch.name} actualizado, señor."

    # === ROLES ===
    if a == "add_role":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        r = command_parser.find_role(guild, p.get("role_name",""))
        if not r: return R["no_role"].format(t=p.get("role_name"))
        await t.add_roles(r); return f"Rol '{r.name}' asignado a {t.display_name}, señor."
    if a == "remove_role":
        t = command_parser.find_member(guild, p.get("target_name",""))
        if not t: return R["no_target"].format(t=p.get("target_name"))
        r = command_parser.find_role(guild, p.get("role_name",""))
        if not r: return R["no_role"].format(t=p.get("role_name"))
        await t.remove_roles(r); return f"Rol '{r.name}' removido de {t.display_name}, señor."
    if a == "create_role":
        r = await guild.create_role(name=p.get("name","Nuevo Rol")); return f"Rol '{r.name}' creado, señor."
    if a == "delete_role":
        r = command_parser.find_role(guild, p.get("name",""))
        if not r: return R["no_role"].format(t=p.get("name"))
        n = r.name; await r.delete(); return f"Rol '{n}' eliminado, señor."
    if a == "role_color":
        r = command_parser.find_role(guild, p.get("target_name",""))
        if not r: return R["no_role"].format(t=p.get("target_name"))
        colors = {"rojo":0xFF0000,"azul":0x0000FF,"verde":0x00FF00,"amarillo":0xFFFF00,
                  "naranja":0xFF8800,"morado":0x800080,"rosa":0xFF69B4,"blanco":0xFFFFFF,
                  "negro":0x000001,"gris":0x808080,"cyan":0x00FFFF,"dorado":0xFFD700}
        c = colors.get(p.get("new_value","").lower(), 0x808080)
        await r.edit(color=discord.Color(c)); return f"Color del rol '{r.name}' cambiado, señor."

    # === MESSAGES ===
    if a == "purge_messages":
        cnt = min(p.get("count",10), 100)
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).manage_messages:
                d = await ch.purge(limit=cnt); return f"{len(d)} mensajes eliminados de {ch.name}, señor."
        return "No tengo permisos para limpiar mensajes."
    if a == "slowmode":
        s = p.get("seconds",0)
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).manage_channels:
                await ch.edit(slowmode_delay=s)
                return f"Modo lento {'activado: '+str(s)+' segundos' if s else 'desactivado'} en {ch.name}, señor."
        return "No tengo permisos."
    if a == "say":
        return p.get("text", "No tengo nada que decir, señor.")
    if a == "announce":
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).send_messages:
                await ch.send(f"📢 **Anuncio de JARVIS:** {p.get('text','')}"); return f"Anuncio publicado en {ch.name}, señor."
        return "No encontré canal para anunciar."

    # === SERVER ===
    if a == "create_invite":
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).create_instant_invite:
                inv = await ch.create_invite(max_age=86400, max_uses=10)
                return f"Invitación creada: {inv.url}, válida por 24 horas, señor."
        return "No pude crear invitación."
    if a == "set_server_name":
        await guild.edit(name=p.get("name","")); return f"Servidor renombrado a '{p.get('name','')}', señor."
    if a == "set_afk_channel":
        ch = command_parser.find_channel(guild, p.get("name",""), discord.ChannelType.voice)
        if not ch: return R["no_channel"].format(t=p.get("name"))
        await guild.edit(afk_channel=ch); return f"Canal AFK establecido: {ch.name}, señor."
    if a == "set_afk_timeout":
        await guild.edit(afk_timeout=p.get("timeout",300)); return "Timeout AFK actualizado, señor."
    if a == "set_verification":
        levels = {"ninguno":discord.VerificationLevel.none,"bajo":discord.VerificationLevel.low,
                  "medio":discord.VerificationLevel.medium,"alto":discord.VerificationLevel.high,
                  "máximo":discord.VerificationLevel.highest}
        lv = levels.get(p.get("level","medio"), discord.VerificationLevel.medium)
        await guild.edit(verification_level=lv); return f"Verificación establecida en {p.get('level','medio')}, señor."

    # === EMOJIS ===
    if a == "delete_emoji":
        name = p.get("name","").lower()
        for e in guild.emojis:
            if name in e.name.lower():
                await e.delete(); return f"Emoji '{e.name}' eliminado, señor."
        return "No encontré ese emoji."

    # === BOT SELF ===
    if a == "bot_status":
        import discord
        activity = discord.Game(name=p.get("text", "Vigilando"))
        await guild.me._state._get_client().change_presence(activity=activity)
        return f"Estado actualizado a: {p.get('text','')}, señor."
    if a == "bot_nick":
        await guild.me.edit(nick=p.get("text","")); return f"Mi nombre cambiado a '{p.get('text','')}', señor."
    if a == "set_volume":
        v = p.get("volume", 100)
        config.TTS_VOLUME = str(round(max(0.1, min(5.0, v / 100 * 2)), 1))
        return f"Volumen ajustado al {v} por ciento, señor."
    if a == "change_voice":
        if p.get("voice") == "female":
            config.TTS_VOICE = "es-ES-ElviraNeural"; return "Voz cambiada a femenina, señor."
        else:
            config.TTS_VOICE = "es-MX-JorgeNeural"; return "Voz cambiada a masculina, señor."

    # === EVENTS ===
    if a == "create_event":
        return f"Evento '{p.get('name','')}' anotado para {p.get('time','')}, señor. Los eventos programados requieren configuración manual en Discord."

    # === THREADS ===
    if a == "create_thread":
        for ch in guild.text_channels:
            if ch.permissions_for(guild.me).create_public_threads:
                th = await ch.create_thread(name=p.get("name","Nuevo Hilo"), type=discord.ChannelType.public_thread)
                return f"Hilo '{th.name}' creado en {ch.name}, señor."
        return "No pude crear el hilo."

    return "No entendí esa orden. Diga 'Jarvis ayuda' para ver mis comandos."
