import os
import unittest
from unittest.mock import Mock, patch

import track


class GreenApiTests(unittest.TestCase):
    def green_env(self, **overrides):
        values = {
            "WHATSAPP_PHONE": "+55 (12) 98841-6345",
            "GREEN_API_INSTANCE_ID": "1234567890",
            "GREEN_API_TOKEN": "token-secreto",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=True)

    def test_send_whatsapp_uses_green_api_payload(self):
        response = Mock(ok=True, status_code=200, text='{"idMessage":"abc"}')

        with self.green_env(), patch.object(track.requests, "post", return_value=response) as post:
            track.send_whatsapp("Encomenda atualizada 📦")

        post.assert_called_once_with(
            "https://api.green-api.com/waInstance1234567890/sendMessage/token-secreto",
            headers={"Content-Type": "application/json"},
            json={"chatId": "5512988416345@c.us", "message": "Encomenda atualizada 📦"},
            timeout=30,
        )

    def test_send_whatsapp_rejects_phone_without_digits(self):
        with self.green_env(WHATSAPP_PHONE="---"), patch.object(track.requests, "post") as post:
            with self.assertRaisesRegex(RuntimeError, "numero valido"):
                track.send_whatsapp("teste")

        post.assert_not_called()

    def test_api_error_does_not_expose_token_in_exception(self):
        response = Mock(ok=False, status_code=401, text="Unauthorized")

        with self.green_env(), patch.object(track.requests, "post", return_value=response):
            with self.assertRaises(RuntimeError) as caught:
                track.send_whatsapp("teste")

        self.assertNotIn("token-secreto", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
