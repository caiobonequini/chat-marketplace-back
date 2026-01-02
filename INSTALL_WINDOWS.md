# Instalação no Windows

## Problema com webrtcvad

O pacote `webrtcvad` requer compilação C++ e pode falhar no Windows se você não tiver as ferramentas de build instaladas.

## Opções de Instalação

### Opção 1: Instalar Microsoft Visual C++ Build Tools (Recomendado)

1. Baixe e instale o [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Durante a instalação, selecione "Desktop development with C++"
3. Após instalar, execute novamente:
   ```bash
   pip install -r requirements.txt
   ```

### Opção 2: Usar sem VAD (Funcionalidade Limitada)

O código foi modificado para funcionar sem `webrtcvad`. O VAD (Voice Activity Detection) será desabilitado e o sistema assumirá que sempre há fala nos chunks de áudio.

**Limitações:**
- O backend não detectará automaticamente início/fim de fala
- Você precisará confiar no frontend para detectar quando o usuário começa/para de falar
- As mensagens `start_speaking` e `stop_speaking` do frontend serão essenciais

**Para usar sem VAD:**
1. O `requirements.txt` já está configurado para não instalar `webrtcvad` por padrão
2. Execute: `pip install -r requirements.txt`
3. O sistema funcionará normalmente, mas sem detecção automática de fala no backend

### Opção 3: Usar Ambiente Virtual Linux/WSL

Se você tiver WSL (Windows Subsystem for Linux) instalado:

```bash
wsl
pip install -r requirements.txt
```

## Verificação

Após a instalação, você pode verificar se o VAD está disponível verificando os logs ao iniciar o servidor. Se você ver:

```
WARNING: VAD desabilitado - webrtcvad não disponível
```

Significa que o VAD está desabilitado e você precisará confiar no frontend para detectar fala.

## Nota

O sistema foi projetado para funcionar com ou sem VAD. A detecção de fala pode ser feita tanto no frontend quanto no backend. Para melhor experiência, recomenda-se fazer a detecção no frontend usando a Web Audio API.

