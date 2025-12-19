# RFID Middleware - Chainway R6 Pro

Aplicativo Android para leitura de tags RFID e codigos de barras usando o coletor Chainway R6 Pro.

## Funcionalidades

- Leitura de tags RFID UHF
- Leitura de codigos de barras 1D/2D
- Ajuste de potencia da antena (5-30 dBm)
- Monitoramento de nivel de bateria
- Sincronizacao com servidor backend
- Armazenamento local de leituras (offline)

## Pre-requisitos

1. **Android Studio** - Arctic Fox (2020.3.1) ou superior
2. **JDK 17** ou superior
3. **Android SDK** - API Level 24+ (Android 7.0 Nougat)
4. **Gradle** - 8.0+

---

## GERANDO O APK

### Metodo 1: Via Android Studio (Recomendado)

1. **Abrir o projeto:**
   ```
   File > Open > C:\Projeto_reavaliacao\middleware_rfid\RfidMiddleware
   ```

2. **Aguardar sincronizacao do Gradle:**
   - O Android Studio baixara as dependencias automaticamente
   - Aguarde a barra de progresso na parte inferior finalizar

3. **Gerar APK de Debug (para testes):**
   ```
   Build > Build Bundle(s) / APK(s) > Build APK(s)
   ```

4. **Localizacao do APK gerado:**
   ```
   app/build/outputs/apk/debug/app-debug.apk
   ```

### Metodo 2: Via Linha de Comando

```bash
# Navegar ate a pasta do projeto
cd C:\Projeto_reavaliacao\middleware_rfid\RfidMiddleware

# Gerar APK de Debug
./gradlew assembleDebug

# Gerar APK de Release (requer keystore configurado)
./gradlew assembleRelease
```

O APK sera gerado em:
- Debug: `app/build/outputs/apk/debug/app-debug.apk`
- Release: `app/build/outputs/apk/release/app-release.apk`

---

## INSTALANDO NO DISPOSITIVO

### Via USB (ADB)

1. Conectar o Chainway R6 Pro via cabo USB
2. Habilitar "Depuracao USB" no dispositivo:
   - Configuracoes > Sobre o telefone > Tocar 7x em "Numero da compilacao"
   - Configuracoes > Opcoes do desenvolvedor > Depuracao USB
3. Executar:
   ```bash
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```

### Via Transferencia de Arquivo

1. Copiar o APK para o dispositivo via USB ou Bluetooth
2. No dispositivo, abrir um gerenciador de arquivos
3. Navegar ate o APK e tocar para instalar
4. Permitir instalacao de fontes desconhecidas se solicitado

---

## CONFIGURACAO INICIAL DO APP

1. **Abrir o aplicativo** no Chainway R6 Pro

2. **Configurar Servidor:**
   - Tocar no icone de engrenagem (Configuracoes)
   - Inserir URL do Servidor:
     - Producao: `https://backend-production-78bb.up.railway.app`
     - Desenvolvimento Local: `http://IP_DO_PC:8000`
   - Inserir Token de Autenticacao (JWT do usuario logado)
   - Salvar

3. **Ajustar Potencia da Antena:**
   - Na tela de Configuracoes
   - Slider de 5 a 30 dBm
   - Menor potencia = menor alcance, menos interferencia
   - Maior potencia = maior alcance, mais tags simultaneas

4. **Conectar ao Leitor:**
   - Na tela principal, tocar em "Escanear Dispositivos"
   - Aguardar o R6 aparecer na lista
   - Tocar no dispositivo para conectar

---

## USO DO APLICATIVO

### Leitura RFID

1. Conectar ao dispositivo R6
2. Tocar em "Iniciar Leitura"
3. Selecionar modo "RFID" no toggle
4. Pressionar o gatilho fisico do R6 ou tocar em "Ler"
5. Apontar para as tags RFID
6. Tags lidas aparecerao na lista

### Leitura de Codigo de Barras

1. Conectar ao dispositivo R6
2. Tocar em "Iniciar Leitura"
3. Selecionar modo "Barcode" no toggle
4. Pressionar o gatilho fisico do R6 ou tocar em "Ler"
5. Apontar para o codigo de barras
6. Codigos lidos aparecerao na lista

### Sincronizacao

1. Apos leituras, tocar em "Salvar" para armazenar localmente
2. Tocar em "Enviar" para sincronizar com o servidor
3. O contador de "Pendentes" mostra itens nao sincronizados

---

## ESTRUTURA DO PROJETO

```
RfidMiddleware/
├── app/
│   ├── libs/                          # SDKs do Chainway
│   │   ├── DeviceAPI_ver20220518_release.aar
│   │   └── cwDeviceAPI20220518.jar
│   └── src/main/
│       ├── java/com/reavaliacao/rfidmiddleware/
│       │   ├── rfid/
│       │   │   └── RfidManager.kt     # Wrapper do SDK
│       │   ├── ui/
│       │   │   ├── screens/           # Telas Compose
│       │   │   ├── theme/             # Tema Material 3
│       │   │   └── MainViewModel.kt   # ViewModel principal
│       │   ├── data/
│       │   │   ├── local/             # Room Database
│       │   │   ├── remote/            # API Service
│       │   │   └── repository/        # Repositorio
│       │   ├── di/                    # Hilt DI modules
│       │   ├── service/               # Background services
│       │   └── MainActivity.kt
│       └── res/                       # Recursos Android
└── build.gradle.kts
```

---

## API DO SERVIDOR

O app envia dados para o endpoint:

```
POST /api/rfid/tags
Authorization: Bearer {token}
Content-Type: application/json

{
    "device_id": "R6-XX:XX:XX:XX:XX:XX",
    "tags": [
        {
            "epc": "E200001234567890",
            "rssi": "-45",
            "timestamp": "2024-12-19T10:30:00Z"
        }
    ],
    "batch_id": "uuid-do-lote",
    "location": null
}
```

---

## SOLUCAO DE PROBLEMAS

### APK nao instala
- Verificar se "Fontes desconhecidas" esta habilitado
- Verificar espaco de armazenamento
- Desinstalar versao anterior se existir

### Dispositivo nao aparece no scan
- Verificar se Bluetooth esta ligado
- Verificar permissoes do app (Bluetooth, Localizacao)
- Reiniciar o R6 Pro

### Leitura RFID nao funciona
- Verificar se esta conectado ao dispositivo
- Verificar nivel de bateria do R6
- Ajustar potencia da antena
- Reiniciar conexao

### Erro de sincronizacao
- Verificar URL do servidor
- Verificar token de autenticacao
- Verificar conexao com internet

---

## TECNOLOGIAS

- **Kotlin** - Linguagem principal
- **Jetpack Compose** - UI declarativa
- **Material 3** - Design system
- **Hilt** - Injecao de dependencia
- **Room** - Persistencia local
- **Retrofit** - Cliente HTTP
- **Coroutines/Flow** - Programacao assincrona
- **Chainway SDK** - Integracao com hardware
