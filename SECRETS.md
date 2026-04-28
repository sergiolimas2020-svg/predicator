# PREDIKTOR — Secrets de GitHub Actions

Documentación de todos los secrets necesarios para que el workflow diario funcione correctamente.

**Configurar en:** https://github.com/sergiolimas2020-svg/predicator/settings/secrets/actions

---

## 🔴 CRÍTICOS — sin estos, el workflow aborta

### `ODDS_API_KEY`

**Qué hace:** Autentica con The Odds API para descargar cuotas reales de bookmakers.

**Usado por:**
- `scrapers/fetch_odds.py` (descarga cuotas diarias)
- `scrapers/generate_predictions.py` (props NBA opcional)

**Cómo obtenerlo:**
1. Registrarse en https://the-odds-api.com/
2. Free tier: 500 requests/mes
3. Plan Starter: $30/mes, 20K requests
4. La key aparece en el dashboard tras confirmar email

**Cómo renovarlo:**
- Si se agotó (errores 401/429): ir al dashboard y rotar la key
- Si quieres más volumen: actualizar al plan Starter
- **Aviso:** el free tier resetea el 1° de cada mes automáticamente

**Cómo validar:**
```bash
curl "https://api.the-odds-api.com/v4/sports/?apiKey=TU_KEY"
# 200 OK → válida | 401 → inválida | 429 → créditos agotados
```

---

### `TELEGRAM_BOT_TOKEN`

**Qué hace:** Token del bot de Telegram que publica picks en el canal.

**Usado por:**
- `bot/telegram_bot.py` (publicación principal)
- `scripts/notify_telegram.py` (alertas al admin)
- `scripts/verify_secrets.py` (validación)

**Cómo obtenerlo:**
1. Hablar con [@BotFather](https://t.me/BotFather) en Telegram
2. Comando `/newbot` → seguir instrucciones
3. Copiar el token (formato `1234567890:ABCdef...`)

**Cómo renovarlo:**
- Si se filtró: `/revoke` en BotFather → genera token nuevo
- Hay que actualizarlo aquí en GitHub Secrets cuando rota

**Cómo validar:**
```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
# {"ok": true, "result": {...}} → válido
```

---

### `TELEGRAM_CHANNEL_ID`

**Qué hace:** Identificador del canal público donde se publican los picks.

**Usado por:**
- `bot/telegram_bot.py`
- `bot/publish.py`

**Valor actual esperado:** `@prediktorcol`

**Cómo obtenerlo:**
- Para canales públicos: `@nombre_del_canal` (con el @)
- Para canales privados: ID numérico negativo (`-1001234567890`)
- El bot debe ser **administrador** del canal con permiso de publicar

**Cómo validar:**
```bash
curl "https://api.telegram.org/bot${TOKEN}/getChat?chat_id=${CHANNEL_ID}"
```

---

## 🟡 OPCIONALES — recomendados pero no bloquean

### `TELEGRAM_ADMIN_CHAT_ID`

**Qué hace:** ID del chat personal del admin (Sergio) para recibir alertas de errores y resúmenes del workflow.

**Usado por:** `scripts/notify_telegram.py`

**Cómo obtenerlo:**
1. Hablar con [@userinfobot](https://t.me/userinfobot) en Telegram
2. El bot responde con tu chat ID (un número como `123456789`)
3. **Importante:** debes haber hablado con tu bot de PREDIKTOR previamente (mandarle un `/start`)
   para que el bot pueda escribirte. Si no, las notificaciones fallan.

**Comportamiento si falta:**
- Las notificaciones se loguean a stdout pero NO se envían
- El workflow funciona normal pero no recibes alertas
- Sin alertas → tienes que checkear manualmente el estado en GitHub Actions

---

### `RAPIDAPI_KEY`

**Qué hace:** Acceso a APIs auxiliares (NBA Games, NBA Players, TechCorner para corners).

**Usado por:** `data_sources/*.py` (módulos de enriquecimiento de contexto)

**Cómo obtenerlo:**
1. https://rapidapi.com/
2. Suscribirse a las APIs específicas (algunas free, otras pagas)

**Comportamiento si falta:**
- El motor publica picks normalmente con datos básicos
- Solo se pierde el contexto enriquecido (estadísticas extra de jugadores)
- No es bloqueante para producción

---

## ⚙️ Cómo configurar un secret en GitHub

1. Ir a https://github.com/sergiolimas2020-svg/predicator/settings/secrets/actions
2. Click **"New repository secret"**
3. Name: copiar exactamente uno de los nombres de arriba
4. Value: pegar el valor sin espacios
5. **"Add secret"**

Para actualizar uno existente: click en el lápiz ✏️ al lado del secret.

---

## 🔍 Cómo verificar que todos los secrets están bien

El workflow corre `scripts/verify_secrets.py` como primer paso. Si falla, aborta antes de quemar créditos de API. Para correr la verificación manualmente:

```bash
export ODDS_API_KEY="..."
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHANNEL_ID="@prediktorcol"
python3 scripts/verify_secrets.py
```

**Exit codes:**
- `0` → todos los críticos OK
- `1` → al menos uno falló (workflow debería abortar)

---

## 🚨 Política de seguridad

- **Nunca commitear secrets** al repositorio. El `.env` local está en `.gitignore`.
- **Nunca compartir secrets en chats** (incluyendo IA). Si por error se comparte, **rotar inmediatamente**.
- **Tokens de GitHub (`ghp_*`)** no deben usarse en este proyecto — el workflow usa `GITHUB_TOKEN` automático.
- Si un secret se filtra: rotarlo en su provider, actualizarlo aquí, y el workflow debería funcionar al próximo run.
