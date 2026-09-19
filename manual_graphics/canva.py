"""ImageGEN Canva OAuth token provider with secret rotation on GitHub."""
import base64
import os
import time

import requests
from nacl import encoding, public


class CanvaTokenError(RuntimeError):
    pass


class CanvaTokenProvider:
    def __init__(self, env=None, session=None):
        env = os.environ if env is None else env
        self.client_id = env.get('IMAGEGEN_CANVA_CLIENT_ID', '').strip()
        self.client_secret = env.get('IMAGEGEN_CANVA_CLIENT_SECRET', '').strip()
        self.refresh_token = env.get('IMAGEGEN_CANVA_REFRESH_TOKEN', '').strip()
        self.github_pat = env.get('IMAGEGEN_GH_PAT', '').strip()
        self.repository = env.get('GITHUB_REPOSITORY', '').strip()
        self.session = session or requests.Session()
        self.access_token = ''
        self.expires_at = 0.0

    def _check_config(self):
        missing = [
            name for name, value in (
                ('IMAGEGEN_CANVA_CLIENT_ID', self.client_id),
                ('IMAGEGEN_CANVA_CLIENT_SECRET', self.client_secret),
                ('IMAGEGEN_CANVA_REFRESH_TOKEN', self.refresh_token),
                ('IMAGEGEN_GH_PAT', self.github_pat),
                ('GITHUB_REPOSITORY', self.repository),
            )
            if not value
        ]
        if missing:
            raise CanvaTokenError(
                'Configurazione Canva mancante: ' + ', '.join(missing)
            )

    def _github_headers(self):
        return {
            'Authorization': f'Bearer {self.github_pat}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    def _sync_secret(self, token):
        base = f'https://api.github.com/repos/{self.repository}/actions/secrets'
        headers = self._github_headers()

        key_response = self.session.get(
            f'{base}/public-key',
            headers=headers,
            timeout=20,
        )
        if key_response.status_code != 200:
            raise CanvaTokenError(
                f'IMAGEGEN_GH_PAT non può leggere la chiave Secrets: HTTP {key_response.status_code}'
            )

        key_data = key_response.json()
        public_key = public.PublicKey(
            key_data['key'].encode(),
            encoding.Base64Encoder(),
        )
        encrypted = public.SealedBox(public_key).encrypt(token.encode())

        payload = {
            'key_id': key_data['key_id'],
            'encrypted_value': base64.b64encode(encrypted).decode(),
        }

        for attempt in range(3):
            response = self.session.put(
                f'{base}/IMAGEGEN_CANVA_REFRESH_TOKEN',
                headers=headers,
                json=payload,
                timeout=20,
            )
            if response.status_code in (201, 204):
                return
            if response.status_code >= 500 and attempt < 2:
                time.sleep(2 + attempt)
                continue
            raise CanvaTokenError(
                'IMAGEGEN_GH_PAT non può aggiornare IMAGEGEN_CANVA_REFRESH_TOKEN: '
                f'HTTP {response.status_code}'
            )

    def refresh_access_token(self):
        now = time.time()
        if self.access_token and self.expires_at > now + 60:
            return self.access_token

        self._check_config()

        # Prima verifica che il PAT riesca davvero a scrivere i secret.
        self._sync_secret(self.refresh_token)

        response = self.session.post(
            'https://api.canva.com/rest/v1/oauth/token',
            auth=(self.client_id, self.client_secret),
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
            },
            timeout=25,
        )
        if response.status_code != 200:
            raise CanvaTokenError(
                f'OAuth Canva HTTP {response.status_code}: {response.text[:300]}'
            )

        payload = response.json()
        new_access = str(payload.get('access_token') or '')
        new_refresh = str(payload.get('refresh_token') or '')
        expires_in = int(payload.get('expires_in') or 0)

        if not new_access or not new_refresh:
            raise CanvaTokenError('Risposta OAuth Canva incompleta')

        self._sync_secret(new_refresh)

        self.refresh_token = new_refresh
        self.access_token = new_access
        self.expires_at = now + max(60, expires_in - 60)
        return self.access_token
