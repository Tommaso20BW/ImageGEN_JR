"""Manual workflow to refresh the Canva token and update the GitHub secret."""
from canva import CanvaTokenProvider


def main():
    provider = CanvaTokenProvider()
    provider.refresh_access_token()
    print('OK IMAGEGEN: refresh token Canva aggiornato correttamente.', flush=True)


if __name__ == '__main__':
    main()
