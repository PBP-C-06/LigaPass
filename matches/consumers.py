import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MatchConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.match_api_id = self.scope['url_route']['kwargs']['match_api_id']
        self.match_group_name = f'match_{self.match_api_id}'

        # Masuk ke grup match
        await self.channel_layer.group_add(
            self.match_group_name,
            self.channel_name
        )

        await self.accept()
        print(f"WebSocket terhubung untuk match {self.match_api_id}")

    async def disconnect(self, close_code):
        # Keluar dari grup
        await self.channel_layer.group_discard(
            self.match_group_name,
            self.channel_name
        )
        print(f"WebSocket terputus untuk match {self.match_api_id}")

    # Menerima pesan dari WebSocket (kita tidak butuh ini)
    async def receive(self, text_data):
        pass

    # Menerima pesan dari grup match (dari worker)
    async def match_update(self, event):
        message = event['message']

        # Kirim pesan ke WebSocket (ke browser pengguna)
        await self.send(text_data=json.dumps(message))