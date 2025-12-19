# Plano - Middleware RFID Chainway R6 Pro

## 1. Visao Geral

APK Android que funciona como middleware entre o coletor RFID Chainway R6 Pro e a aplicacao web de inventario.

```
[Chainway R6 Pro] <--BLE--> [APK Middleware] <--HTTP/WebSocket--> [Aplicacao Web]
```

## 2. Analise do SDK Chainway

### 2.1 Bibliotecas Disponiveis
- `DeviceAPI_ver20220518_release.aar` (2.5 MB) - SDK principal
- `cwDeviceAPI20220518.jar` (1 MB) - API complementar

### 2.2 Classes Principais do SDK
```java
// Pacote: com.rscja.deviceapi
RFIDWithUHFBLE           // Classe principal de comunicacao
UHFTAGInfo               // Entidade com dados da tag (EPC, RSSI)
ConnectionStatus         // Enum: CONNECTED, DISCONNECTED
ConnectionStatusCallback // Callback de status conexao
ScanBTCallback           // Callback de scan Bluetooth
KeyEventCallback         // Callback do botao fisico do coletor
```

### 2.3 Funcoes do SDK
| Funcao | Descricao |
|--------|-----------|
| `uhf.init(context)` | Inicializa SDK |
| `uhf.startScanBTDevices(callback)` | Escaneia dispositivos BLE |
| `uhf.stopScanBTDevices()` | Para scan BLE |
| `uhf.connect(address, callback)` | Conecta ao R6 |
| `uhf.disconnect()` | Desconecta |
| `uhf.getConnectStatus()` | Retorna status |
| `uhf.startInventoryTag()` | Inicia leitura continua |
| `uhf.stopInventory()` | Para leitura |
| `uhf.inventorySingleTag()` | Le uma tag |
| `uhf.readTagFromBufferList()` | Le buffer de tags |
| `uhf.setPower(int)` | Define potencia (5-30 dBm) |

### 2.4 Dados da Tag RFID
```java
UHFTAGInfo {
    getEPC()   // Codigo EPC da tag (ex: "E200001234567890")
    getRssi()  // Intensidade do sinal
    getTid()   // ID da tag (opcional)
}
```

## 3. Arquitetura do Middleware

### 3.1 Telas do App
```
1. Splash Screen
   └── Verifica permissoes (Bluetooth, Location)

2. Tela Principal
   ├── Status conexao (conectado/desconectado)
   ├── Dispositivo conectado (nome/MAC)
   ├── Botao: Escanear dispositivos BLE
   ├── Botao: Conectar/Desconectar
   ├── URL do servidor web (configuravel)
   └── Status sincronizacao

3. Tela Leitura RFID
   ├── Lista de tags lidas (EPC, RSSI, timestamp)
   ├── Contador de tags
   ├── Botao: Iniciar/Parar leitura
   ├── Botao: Limpar lista
   └── Botao: Enviar para servidor

4. Tela Configuracoes
   ├── URL da API web
   ├── Token de autenticacao
   ├── Potencia do leitor (5-30 dBm)
   ├── Modo de envio (automatico/manual)
   └── Intervalo de sincronizacao
```

### 3.2 Fluxo de Dados
```
[R6 le tag]
    → [SDK retorna UHFTAGInfo]
    → [App processa e armazena local]
    → [Envia para API web via HTTP POST]
```

### 3.3 API de Comunicacao com Web

**Endpoint sugerido na aplicacao web:**
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
    "batch_id": "uuid",
    "location": "Setor A"
}
```

## 4. Stack Tecnologica

| Componente | Tecnologia |
|------------|------------|
| Linguagem | Kotlin |
| Min SDK | Android 8.0 (API 26) |
| UI | Jetpack Compose |
| HTTP Client | Retrofit + OkHttp |
| Storage Local | Room Database |
| DI | Hilt |
| Bluetooth | SDK Chainway |

## 5. Estrutura do Projeto Android

```
app/
├── src/main/
│   ├── java/com/reavaliacao/rfidmiddleware/
│   │   ├── MainActivity.kt
│   │   ├── ui/
│   │   │   ├── screens/
│   │   │   │   ├── SplashScreen.kt
│   │   │   │   ├── MainScreen.kt
│   │   │   │   ├── ReadingScreen.kt
│   │   │   │   └── SettingsScreen.kt
│   │   │   ├── components/
│   │   │   │   ├── TagListItem.kt
│   │   │   │   └── StatusIndicator.kt
│   │   │   └── theme/
│   │   ├── data/
│   │   │   ├── local/
│   │   │   │   ├── AppDatabase.kt
│   │   │   │   ├── TagEntity.kt
│   │   │   │   └── TagDao.kt
│   │   │   ├── remote/
│   │   │   │   ├── ApiService.kt
│   │   │   │   └── TagDto.kt
│   │   │   └── repository/
│   │   │       └── TagRepository.kt
│   │   ├── rfid/
│   │   │   ├── RfidManager.kt        // Wrapper do SDK
│   │   │   ├── RfidCallback.kt
│   │   │   └── BluetoothScanner.kt
│   │   ├── service/
│   │   │   └── SyncService.kt        // Sincronizacao em background
│   │   └── di/
│   │       └── AppModule.kt
│   ├── libs/
│   │   └── DeviceAPI_ver20220518_release.aar
│   └── AndroidManifest.xml
└── build.gradle.kts
```

## 6. Fases de Implementacao

### Fase 1: Setup Projeto
- [ ] Criar projeto Android Studio (Kotlin + Compose)
- [ ] Configurar Gradle com dependencias
- [ ] Importar SDK Chainway (.aar)
- [ ] Configurar permissoes no Manifest

### Fase 2: Integracao Bluetooth/RFID
- [ ] Implementar RfidManager (wrapper do SDK)
- [ ] Scan de dispositivos BLE
- [ ] Conexao/desconexao com R6
- [ ] Leitura de tags RFID
- [ ] Tratamento de eventos do botao fisico

### Fase 3: Interface do Usuario
- [ ] Tela principal com status
- [ ] Tela de leitura com lista de tags
- [ ] Tela de configuracoes
- [ ] Indicadores visuais de conexao

### Fase 4: Comunicacao com Web
- [ ] Configurar Retrofit
- [ ] Implementar envio de tags
- [ ] Autenticacao via token
- [ ] Tratamento de erros/retry

### Fase 5: Persistencia Local
- [ ] Configurar Room Database
- [ ] Cache de tags nao sincronizadas
- [ ] Sincronizacao offline-first

### Fase 6: Polimento
- [ ] Notificacoes de status
- [ ] Som/vibracao ao ler tag
- [ ] Testes em dispositivo real
- [ ] Geracao do APK release

## 7. Dependencias Gradle

```kotlin
dependencies {
    // SDK Chainway
    implementation(files("libs/DeviceAPI_ver20220518_release.aar"))

    // Android Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")

    // Compose
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation(platform("androidx.compose:compose-bom:2024.02.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.navigation:navigation-compose:2.7.7")

    // Retrofit
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    // Room
    implementation("androidx.room:room-runtime:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    kapt("androidx.room:room-compiler:2.6.1")

    // Hilt
    implementation("com.google.dagger:hilt-android:2.50")
    kapt("com.google.dagger:hilt-compiler:2.50")
}
```

## 8. Permissoes Android

```xml
<uses-permission android:name="android.permission.BLUETOOTH" />
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
```

## 9. Proximos Passos

1. **Voce precisa fornecer:**
   - URL base da sua API web
   - Estrutura do endpoint para receber tags
   - Metodo de autenticacao (token, login?)

2. **Eu preciso:**
   - Android Studio instalado na maquina
   - Dispositivo Android ou emulador para testes
   - Coletor Chainway R6 Pro para testes reais

## 10. Recursos

- SDK Reference: `/middleware_rfid/chainway_reference/`
- SDK Libraries: `/middleware_rfid/chainway_reference/android/src/main/libs/`
- Exemplo de integracao: `RfidChainwayR6Module.java`
