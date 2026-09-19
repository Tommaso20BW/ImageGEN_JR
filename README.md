# ImageGEN JR

Bot Telegram dedicato esclusivamente alla generazione manuale delle grafiche JR.

## Funzionamento

1. Avvia manualmente il workflow **ImageGen**.
2. Il bot invia **🎨 Apri generatore** alla chat configurata.
3. Compila la Mini App.
4. Premi **GENERA GRAFICA**.
5. Il PNG viene inviato nella stessa chat.
6. Il servizio termina automaticamente dopo 30 minuti.

Il bot è separato dal LiveScore e usa un token Telegram dedicato.

## Secrets richiesti

- `MANUAL_GRAPHICS_TELEGRAM_TOKEN`
- `MANUAL_GRAPHICS_TELEGRAM_CHAT_ID`
- `CANVA_CLIENT_ID`
- `CANVA_CLIENT_SECRET`
- `CANVA_REFRESH_TOKEN`
- `GH_PAT`

`GH_PAT` serve esclusivamente a salvare il nuovo refresh token Canva nel secret
`CANVA_REFRESH_TOKEN`. Non viene usato alcun Gist per coordinare Telegram.
