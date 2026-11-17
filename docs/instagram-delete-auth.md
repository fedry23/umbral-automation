# UMBRAL · Autorización independiente para eliminar un Reel

## Estado verificado
- El token de publicación `IG_ACCESS_TOKEN` funciona y NO se sustituye.
- Meta documenta `DELETE /{IG_MEDIA_ID}` para Reels no publicitarios con **Facebook Login for Business**, token de **usuario de Facebook** y permisos `instagram_basic` + `instagram_manage_contents`.
- El permiso `instagram_manage_contents` figura «Listo para prueba» en la aplicación, pero **eso no lo añade al token existente**.
- Reel objetivo único: `18121779709999190`. No ejecutar eliminación hasta tener un sustituto validado.

## Ruta sin backend OAuth ni cuenta publicitaria
1. En [Graph API Explorer](https://developers.facebook.com/tools/explorer/) elegir **UMBRAL Automation** como aplicación y el tipo de token **User Token / token de usuario de Facebook** (no Page Token ni Instagram User Token).
2. Solicitar explícitamente `instagram_basic` y `instagram_manage_contents`. Si Explorer no ofrece el segundo permiso o Meta exige revisión, detenerse; no inventar redirecciones ni pedir permisos extra.
3. Autorizar con el usuario que administra la página vinculada a `@umbral.terror`. El modo de prueba puede limitarse a roles de la aplicación.
4. Verificar en la herramienta de depuración de tokens de Meta que **ambos permisos** están presentes, que el token es válido y pertenece a la aplicación correcta.
5. Guardar el token únicamente en **Settings → Secrets and variables → Actions → New repository secret**, nombre `IG_DELETE_ACCESS_TOKEN`. No compartirlo en chats, capturas, URL públicas ni archivos.
6. Un futuro workflow de eliminación deberá comprobar el ID, la propiedad, la identidad de la cuenta, la existencia de un sustituto validado y una autorización explícita para ese ID antes de emitir cualquier DELETE. Nunca reintentar una eliminación ambigua.

## Sobre GitHub Pages
La ruta `/oauth/callback/` es una **página informativa estática**, NO un servidor OAuth: no canjea códigos ni protege un `client_secret`. **No registrarla como redirección OAuth ni utilizarla para autorizar**. El Explorer de Meta evita tener que construir y operar un backend OAuth propio.

## Fuente
Documentación oficial de Meta: https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/
