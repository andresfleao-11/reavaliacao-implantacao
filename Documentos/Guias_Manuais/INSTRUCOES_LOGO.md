# Instruções para Adicionar a Logo

## Localização do Arquivo
Coloque a imagem da logo em:
```
C:\Projeto_reavaliacao\frontend\public\logo.png
```

## Especificações da Imagem
- **Nome do arquivo:** `logo.png`
- **Formato:** PNG (recomendado para transparência)
- **Tamanho recomendado:** 200x200 pixels ou maior (será redimensionado automaticamente)
- **Proporção:** Quadrada (1:1) ou a logo será distorcida

## Comportamento da Logo

### Menu Expandido (264px)
- Logo aparece com 80x80 pixels
- Centralizada horizontalmente

### Menu Colapsado (80px)
- Logo aparece com 40x40 pixels
- Centralizada horizontalmente
- Transição suave de 300ms

### Posição
- **Localização:** Rodapé do menu lateral
- **Acima de:** Botão de alternância de tema (Modo Claro/Escuro)
- **Padding:** 16px ao redor

## Passos para Adicionar

1. Salve a imagem da logo como `logo.png`
2. Copie o arquivo para `C:\Projeto_reavaliacao\frontend\public\`
3. A logo aparecerá automaticamente (não precisa reiniciar)
4. Se a imagem não aparecer, verifique:
   - Nome do arquivo está correto: `logo.png` (minúsculas)
   - Arquivo está na pasta correta: `frontend/public/`
   - Formato da imagem é válido (PNG, JPG, SVG, etc.)

## Fallback
Se a imagem não for encontrada ou houver erro ao carregar, ela simplesmente não será exibida (sem quebrar o layout).

## Exemplo de Comando para Copiar
```bash
# Windows (PowerShell)
Copy-Item "caminho\da\sua\logo.png" "C:\Projeto_reavaliacao\frontend\public\logo.png"

# Windows (CMD)
copy "caminho\da\sua\logo.png" "C:\Projeto_reavaliacao\frontend\public\logo.png"
```
