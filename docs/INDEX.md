# Índice de Documentação

Bem-vindo à documentação completa do Chat Marketplace Backend!

## 📚 Documentação Principal

### [README.md](../README.md)
Visão geral do projeto, instalação rápida e links para outras documentações.

### [SETUP.md](../SETUP.md)
Guia completo de configuração passo a passo, incluindo:
- Instalação de dependências
- Configuração do Google Cloud
- Variáveis de ambiente
- Troubleshooting

### [INSTALL_WINDOWS.md](../INSTALL_WINDOWS.md)
Guia específico para instalação no Windows, incluindo:
- Problemas com webrtcvad
- Instalação de Microsoft Visual C++ Build Tools
- Alternativas sem VAD

## 🏗️ Arquitetura e Design

### [ARCHITECTURE.md](ARCHITECTURE.md)
Documentação detalhada da arquitetura do sistema:
- Componentes principais
- Fluxo de dados
- Gerenciamento de estado
- Tratamento de erros
- Performance e escalabilidade
- Segurança

## 🔌 API e Integração

### [API.md](../API.md)
Documentação da API WebSocket com:
- Protocolo de mensagens
- Exemplos de uso
- Especificações de áudio
- Tratamento de erros

### [API_REFERENCE.md](API_REFERENCE.md)
Referência completa da API:
- Endpoints HTTP
- Endpoint WebSocket
- Protocolo de mensagens detalhado
- Exemplos de código
- Boas práticas
- Limites e restrições

## 🛠️ Desenvolvimento

### [.cursorrules](../.cursorrules)
Regras e informações essenciais para desenvolvimento:
- Contexto do projeto
- Padrões de código
- Estrutura de diretórios
- Boas práticas
- Comandos úteis

## 📖 Guias Rápidos

### Início Rápido
1. Leia [SETUP.md](../SETUP.md)
2. Configure variáveis de ambiente
3. Execute `python run.py`
4. Teste em `http://localhost:8000/test`

### Integração Frontend
1. Leia [API.md](../API.md)
2. Consulte [API_REFERENCE.md](API_REFERENCE.md) para detalhes
3. Use a página de teste (`/test`) como referência

### Desenvolvimento
1. Leia [ARCHITECTURE.md](ARCHITECTURE.md) para entender o sistema
2. Consulte [.cursorrules](../.cursorrules) para padrões
3. Use os exemplos em `test_websocket.py`

## 🔍 Busca Rápida

### Por Tarefa

**Configuração:**
- [SETUP.md](../SETUP.md) - Configuração geral
- [INSTALL_WINDOWS.md](../INSTALL_WINDOWS.md) - Windows específico

**Desenvolvimento:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - Entender arquitetura
- [.cursorrules](../.cursorrules) - Padrões de código

**Integração:**
- [API.md](../API.md) - Guia de integração
- [API_REFERENCE.md](API_REFERENCE.md) - Referência completa

**Troubleshooting:**
- [SETUP.md](../SETUP.md) - Seção Troubleshooting
- [INSTALL_WINDOWS.md](../INSTALL_WINDOWS.md) - Problemas Windows

### Por Tópico

**WebSocket:**
- [API.md](../API.md) - Protocolo WebSocket
- [API_REFERENCE.md](API_REFERENCE.md) - Referência WebSocket
- [ARCHITECTURE.md](ARCHITECTURE.md) - WebSocket Handler

**Dialogflow:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - Dialogflow Service
- [SETUP.md](../SETUP.md) - Configuração Dialogflow

**Áudio:**
- [API.md](../API.md) - Especificações de áudio
- [ARCHITECTURE.md](ARCHITECTURE.md) - Audio Processor
- [ARCHITECTURE.md](ARCHITECTURE.md) - VAD Service

**Barge-in:**
- [ARCHITECTURE.md](ARCHITECTURE.md) - Barge-in
- [API_REFERENCE.md](API_REFERENCE.md) - Mensagem barge_in

## 📝 Estrutura de Documentação

```
docs/
├── INDEX.md              # Este arquivo
├── ARCHITECTURE.md       # Arquitetura do sistema
└── API_REFERENCE.md      # Referência completa da API

../
├── README.md             # Visão geral
├── SETUP.md              # Guia de configuração
├── INSTALL_WINDOWS.md    # Instalação Windows
├── API.md                # Documentação API WebSocket
└── .cursorrules          # Regras de desenvolvimento
```

## 🆘 Precisa de Ajuda?

1. **Problemas de instalação**: Consulte [SETUP.md](../SETUP.md) ou [INSTALL_WINDOWS.md](../INSTALL_WINDOWS.md)
2. **Dúvidas sobre API**: Veja [API.md](../API.md) ou [API_REFERENCE.md](API_REFERENCE.md)
3. **Entender arquitetura**: Leia [ARCHITECTURE.md](ARCHITECTURE.md)
4. **Padrões de código**: Consulte [.cursorrules](../.cursorrules)

## 📞 Recursos Externos

- [Dialogflow CX Documentation](https://cloud.google.com/dialogflow/cx/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [WebRTC VAD](https://github.com/wiseman/py-webrtcvad)

