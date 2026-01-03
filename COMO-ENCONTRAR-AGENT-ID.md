# Como Encontrar o Agent ID do Dialogflow CX

## 🎯 Método 1: Via URL do Google Cloud Console (Mais Rápido)

Quando você acessa o agente no Google Cloud Console, a URL contém o Agent ID:

```
https://conversational-agents.cloud.google.com/projects/{PROJECT_ID}/locations/{LOCATION}/agents/{AGENT_ID}/...
```

### Exemplo da sua URL:
```
https://conversational-agents.cloud.google.com/projects/mv-ia-472317/locations/us-central1/agents/ee1f79d8-b348-4360-94b5-eb6308f7cef1/...
```

**Agent ID extraído:** `ee1f79d8-b348-4360-94b5-eb6308f7cef1`

## 🔍 Método 2: Via Google Cloud Console

1. Acesse: https://console.cloud.google.com/
2. Selecione o projeto: `mv-ia-472317`
3. Navegue até: **Dialogflow CX** > **Agents**
4. Clique no agente desejado
5. Na URL ou nas configurações, você verá o Agent ID (UUID)

## 📋 Método 3: Via API (gcloud CLI)

```bash
gcloud dialogflow-cx agents list --project=mv-ia-472317 --location=us-central1
```

## ⚙️ Atualizar o .env

Edite o arquivo `.env` e atualize:

```env
DIALOGFLOW_AGENT_ID=ee1f79d8-b348-4360-94b5-eb6308f7cef1
```

**IMPORTANTE:**
- O Agent ID é um **UUID** (não o Display Name)
- O Display Name pode ser "marketplace-ia", mas o ID real é o UUID
- Sempre use o UUID na configuração

## 🔗 Estrutura da URL

```
https://conversational-agents.cloud.google.com/projects/{PROJECT_ID}/locations/{LOCATION}/agents/{AGENT_ID}/...
```

Onde:
- `PROJECT_ID`: `mv-ia-472317`
- `LOCATION`: `us-central1`
- `AGENT_ID`: `ee1f79d8-b348-4360-94b5-eb6308f7cef1` ← **Este é o valor que você precisa!**

