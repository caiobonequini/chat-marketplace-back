"""Script de teste para WebSocket (exemplo)."""
import asyncio
import websockets
import json
import base64
import numpy as np


async def test_websocket():
    """Testa conexão WebSocket."""
    uri = "ws://localhost:8000/ws/voice-chat"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Conectado ao servidor WebSocket")
            
            # Receber mensagem de início de sessão
            response = await websocket.recv()
            message = json.loads(response)
            print(f"Mensagem recebida: {message}")
            
            if message.get('type') == 'session_start':
                session_id = message.get('data', {}).get('session_id')
                print(f"Sessão iniciada: {session_id}")
                
                # Simular envio de chunk de áudio (silêncio)
                # Gerar alguns samples de áudio silencioso
                # Configuração ideal para Vertex AI: LINEAR16 @ 16000 Hz
                sample_rate = 16000
                duration = 0.1  # 100ms
                samples = int(sample_rate * duration)
                audio_data = np.zeros(samples, dtype=np.int16)
                audio_bytes = audio_data.tobytes()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                
                # Enviar chunk de áudio
                audio_message = {
                    "type": "audio_chunk",
                    "session_id": session_id,
                    "data": {
                        "audio": audio_base64
                    }
                }
                await websocket.send(json.dumps(audio_message))
                print("Chunk de áudio enviado")
                
                # Aguardar resposta
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    message = json.loads(response)
                    print(f"Resposta recebida: {message}")
                except asyncio.TimeoutError:
                    print("Timeout aguardando resposta")
            
    except Exception as e:
        print(f"Erro: {e}")


if __name__ == "__main__":
    print("Testando conexão WebSocket...")
    asyncio.run(test_websocket())

