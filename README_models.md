# Media Triage Vault

Sistema local para analisar, classificar, organizar e mover fotos e vídeos de uma biblioteca pessoal, sem envio de arquivos para a internet.

## 1. Objetivo

O projeto deve:

1. Ler recursivamente os arquivos de uma pasta escolhida pelo usuário.
2. Identificar o tipo e a possível origem de cada arquivo.
3. Classificar o tema principal das fotos.
4. Extrair metadados úteis, incluindo localização geográfica.
5. Apresentar os resultados em uma interface web local.
6. Permitir que o usuário escolha uma pasta de destino para cada grupo.
7. Mover os arquivos somente após confirmação.
8. Validar a movimentação e gerar um relatório de sucesso e erros.

Todo o processamento deve ser executado localmente.

---

## 2. Classificações iniciais

O sistema deve separar os arquivos nas seguintes categorias:

- Vídeos.
- Capturas de tela do celular.
- Arquivos recebidos pelo WhatsApp.
- Fotos tiradas por iPhone.
- Fotos em formato RAW.
- Outros tipos de imagens.
- Arquivos não reconhecidos ou com classificação incerta.

As classificações baseadas na origem do arquivo devem priorizar regras e metadados, e não modelos de inteligência artificial.

---

## 3. Identificação por metadados e regras

### 3.1 Fotos tiradas por iPhone

Verificar campos EXIF como:

- `Make`
- `Model`
- `Software`
- `LensModel`
- `DateTimeOriginal`
- `GPSLatitude`
- `GPSLongitude`
- `GPSAltitude`

Exemplos esperados:

```text
Make: Apple
Model: iPhone 15 Pro
Software: 18.x
```

A identificação deve considerar que alguns aplicativos removem ou modificam os metadados.

### 3.2 Arquivos RAW

Identificar inicialmente pelas extensões:

```text
.dng
.cr2
.cr3
.nef
.arw
.raf
.orf
.rw2
.pef
```

Também é recomendável validar o tipo MIME e o conteúdo do arquivo para evitar depender somente da extensão.

### 3.3 Capturas de tela

Combinar diferentes sinais:

- Nome do arquivo.
- Dimensões típicas de telas de celulares.
- Ausência de dados da câmera.
- Campo de software.
- Formato do arquivo.
- Proporção da imagem.
- Padrões visuais, somente quando as regras não forem suficientes.

Exemplos de nomes:

```text
Screenshot
Captura de Tela
IMG_*_screen
```

### 3.4 Arquivos recebidos pelo WhatsApp

Possíveis sinais:

- Nome do arquivo com padrão `IMG-YYYYMMDD-WA####`.
- Nome do vídeo com padrão `VID-YYYYMMDD-WA####`.
- Ausência ou redução de metadados EXIF.
- Compressão característica.
- Dimensões e qualidade alteradas.
- Diretório de origem contendo referências ao WhatsApp.

Essa classificação deve ter um nível de confiança, pois arquivos podem ser renomeados.

### 3.5 Vídeos

Identificar por extensão, tipo MIME e leitura do container.

Exemplos:

```text
.mp4
.mov
.m4v
.avi
.mkv
.3gp
.webm
```

Metadados úteis:

- Codec.
- Duração.
- Resolução.
- Frame rate.
- Data de criação.
- Dispositivo.
- Localização, quando disponível.

---

## 4. Localização geográfica

Para fotos e vídeos com coordenadas GPS:

1. Extrair latitude e longitude dos metadados.
2. Converter coordenadas EXIF para graus decimais.
3. Relacionar as coordenadas ao país.
4. Salvar também estado, cidade ou região quando possível.

Como o projeto deve funcionar offline, o reverse geocoding deve utilizar uma base geográfica local.

Possíveis alternativas:

- GeoNames baixado localmente.
- Natural Earth.
- Banco espacial SQLite/SpatiaLite.
- Shapefiles de fronteiras de países.
- GeoPandas com operação de ponto dentro de polígono.

Fluxo recomendado:

```text
Coordenadas GPS
    ↓
GeoDataFrame com fronteiras
    ↓
Spatial join
    ↓
País identificado
```

Quando não houver coordenadas, o sistema deve registrar:

```text
localizacao_status: sem_dados_gps
```

---

## 5. Identificação do tema principal

A identificação semântica deve ser separada da identificação técnica do arquivo.

Exemplos de temas:

- Família e amigos.
- Viagem.
- Praia.
- Paisagem natural.
- Cidade e arquitetura.
- Comida.
- Animais.
- Evento ou festa.
- Trabalho.
- Documento.
- Produto.
- Veículo.
- Esporte.
- Arte.
- Outros.

---

## 6. Modelos abertos recomendados

### 6.1 SigLIP 2

Modelo recomendado para classificação zero-shot e geração de embeddings:

```text
google/siglip2-so400m-patch14-384
```

Utilizações:

- Comparar uma imagem com uma lista de categorias.
- Escolher o tema mais provável.
- Gerar embeddings.
- Fazer busca semântica.
- Agrupar imagens semelhantes.
- Detectar resultados ambíguos.

Exemplo de categorias:

```python
labels = [
    "família e amigos",
    "viagem",
    "paisagem natural",
    "praia",
    "cidade e arquitetura",
    "comida",
    "animais",
    "evento ou festa",
    "trabalho",
    "documento",
    "produto",
    "veículo",
]
```

O score deve ser tratado como similaridade relativa, e não como probabilidade calibrada.

### 6.2 Qwen3-VL

Modelo recomendado para interpretar imagens livremente e tratar casos ambíguos:

```text
Qwen/Qwen3-VL-4B-Instruct
```

Alternativa com maior qualidade:

```text
Qwen/Qwen3-VL-8B-Instruct
```

Utilizações:

- Identificar o tema sem uma lista completamente fechada.
- Entender ações, ambientes e contexto.
- Produzir descrições.
- Sugerir álbuns.
- Retornar resultados estruturados em JSON.
- Revisar classificações com baixa confiança.

Exemplo de resposta:

```json
{
  "main_theme": "viagem",
  "secondary_themes": [
    "praia",
    "pôr do sol"
  ],
  "scene": "área externa",
  "people_present": true,
  "objects": [
    "mar",
    "areia",
    "guarda-sol"
  ],
  "suggested_album": "Viagens e férias",
  "confidence": 0.89
}
```

### 6.3 Florence-2

Modelo leve recomendado para tarefas complementares:

```text
microsoft/Florence-2-large
```

Utilizações:

- Geração de legendas.
- OCR.
- Detecção de objetos.
- Identificação de documentos.
- Localização de elementos na imagem.
- Processamento rápido em lote.

### 6.4 Embeddings multimodais

Para uma fase posterior, pode ser utilizado:

```text
Qwen/Qwen3-VL-Embedding-2B
```

Utilizações:

- Busca semântica.
- Agrupamento de fotos.
- Identificação de eventos.
- Criação automática de álbuns.
- Recuperação por texto, imagem ou combinação multimodal.

Antes de incorporar um modelo ao projeto, verificar:

- Licença dos pesos.
- Licença para uso comercial.
- Compatibilidade com a versão instalada do PyTorch e Transformers.
- Necessidade de código remoto do repositório.
- Consumo real de VRAM.
- Formatos de quantização disponíveis.

---

## 7. Arquitetura de classificação em cascata

Não é necessário executar um modelo multimodal grande sobre todas as imagens.

Fluxo recomendado:

```text
Arquivo
  ↓
Validação do arquivo
  ↓
Extensão, MIME e metadados
  ↓
Classificação técnica
  ├── vídeo
  ├── screenshot
  ├── WhatsApp
  ├── iPhone
  ├── RAW
  └── outros
  ↓
SigLIP 2
  ↓
Tema e scores de similaridade
  ↓
Resultado confiável?
  ├── Sim → salvar classificação
  └── Não → Qwen3-VL
                  ↓
          análise detalhada em JSON
```

O Florence-2 pode ser executado quando houver necessidade de:

- OCR.
- Detecção de documentos.
- Legendas.
- Análise complementar de objetos.

---

## 8. Estratégia de confiança

Cada classificação deve registrar:

```json
{
  "category": "viagem",
  "confidence": 0.87,
  "method": "siglip2",
  "requires_review": false
}
```

Sugestão inicial:

- Confiança alta: resultado aceito automaticamente.
- Confiança intermediária: análise pelo Qwen3-VL.
- Confiança baixa: revisão manual.
- Diferença pequena entre os dois maiores scores: considerar resultado ambíguo.

Os limites devem ser calibrados com uma amostra real da biblioteca do usuário.

---

## 9. Hardware

Máquina considerada:

- NVIDIA RTX 4090.
- 24 GB de VRAM.
- 32 GB de memória RAM.

Estratégia recomendada:

- SigLIP 2 para a análise em massa.
- Qwen3-VL 4B para casos ambíguos.
- Qwen3-VL 8B quantizado em 4 bits quando for necessária maior qualidade.
- Florence-2 para OCR e legendas.
- Batch configurável conforme o consumo de memória.
- Mixed precision com BF16 ou FP16.
- Quantização somente quando necessária.

Para bibliotecas grandes, evitar manter simultaneamente todos os modelos carregados na GPU.

---

## 10. Stack sugerida

### Backend

- Python.
- FastAPI.
- Pydantic.
- SQLAlchemy ou SQLModel.
- SQLite para o MVP.
- PostgreSQL em uma evolução futura.

### Processamento de mídia

- Pillow.
- Pillow-HEIF.
- ExifTool.
- ExifRead.
- OpenCV.
- FFmpeg.
- ffprobe.
- RawPy.
- python-magic.

### Inteligência artificial

- PyTorch.
- torchvision.
- Transformers.
- Sentence Transformers.
- Accelerate.
- bitsandbytes, quando aplicável.
- ONNX Runtime, para otimizações futuras.
- TensorRT, em uma fase de otimização.

### Interface

- Next.js.
- React.
- TypeScript.
- Tailwind CSS.
- Comunicação com FastAPI via API local.

### Busca e agrupamento

- FAISS.
- HDBSCAN.
- K-Means.
- UMAP.
- NumPy.
- scikit-learn.

---

## 11. Estrutura sugerida do projeto

```text
media-triage-vault/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── classifiers/
│   │   │   ├── metadata_classifier.py
│   │   │   ├── file_type_classifier.py
│   │   │   ├── siglip_classifier.py
│   │   │   ├── qwen_vl_classifier.py
│   │   │   └── florence_classifier.py
│   │   ├── metadata/
│   │   │   ├── exif_reader.py
│   │   │   ├── video_metadata.py
│   │   │   └── geolocation.py
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── scan_service.py
│   │   │   ├── classification_service.py
│   │   │   ├── movement_service.py
│   │   │   └── validation_service.py
│   │   ├── workers/
│   │   ├── config.py
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── package.json
├── data/
│   ├── database/
│   ├── geographic/
│   ├── models/
│   └── cache/
├── reports/
├── scripts/
├── .gitignore
├── docker-compose.yml
└── README.md
```

---

## 12. Banco de dados

Registro sugerido para cada arquivo:

```json
{
  "id": "uuid",
  "source_path": "/biblioteca/IMG_0001.HEIC",
  "filename": "IMG_0001.HEIC",
  "extension": ".heic",
  "mime_type": "image/heic",
  "size_bytes": 4239012,
  "sha256": "hash",
  "media_type": "image",
  "technical_category": "iphone_photo",
  "main_theme": "viagem",
  "secondary_themes": [
    "praia"
  ],
  "classification_method": "siglip2",
  "classification_confidence": 0.91,
  "camera_make": "Apple",
  "camera_model": "iPhone 15 Pro",
  "captured_at": "2025-01-12T15:32:10",
  "latitude": -23.0000,
  "longitude": -43.0000,
  "country": "Brasil",
  "destination_path": null,
  "movement_status": "pending",
  "error_message": null
}
```

---

## 13. Hash e deduplicação

Antes da movimentação, calcular um hash do arquivo, preferencialmente SHA-256.

Utilizações:

- Detectar duplicatas.
- Confirmar integridade após a cópia.
- Evitar sobrescrita indevida.
- Validar que origem e destino possuem o mesmo conteúdo.
- Permitir retomada do processo.

Para grandes bibliotecas, pode ser utilizado um processo em duas etapas:

1. Comparar tamanho do arquivo.
2. Calcular hash completo somente para candidatos a duplicata.

---

## 14. Interface do usuário

A interface deve oferecer:

### Tela de seleção

- Escolha da pasta de origem.
- Opção de incluir subpastas.
- Extensões aceitas.
- Configuração dos modelos.
- Configuração de lote.

### Tela de processamento

- Quantidade total de arquivos.
- Arquivos analisados.
- Velocidade média.
- Uso de CPU, GPU e memória.
- Erros encontrados.
- Possibilidade de pausar ou cancelar.

### Tela de resultados

- Filtros por categoria.
- Filtros por tema.
- Filtros por país.
- Nível de confiança.
- Miniaturas.
- Visualização de metadados.
- Revisão manual.
- Correção da classificação.

### Tela de destinos

Para cada categoria, o usuário deve escolher uma pasta de destino.

Exemplo:

```text
Fotos de iPhone → D:\Fotos\iPhone
WhatsApp        → D:\Fotos\WhatsApp
Screenshots     → D:\Fotos\Screenshots
RAW             → D:\Fotos\RAW
Vídeos          → D:\Videos
```

### Tela de confirmação

Antes de mover:

- Mostrar quantidade de arquivos.
- Mostrar volume total.
- Verificar espaço disponível.
- Alertar sobre conflitos de nomes.
- Exibir uma prévia das operações.
- Solicitar confirmação explícita.

---

## 15. Movimentação segura

A movimentação não deve ser feita diretamente sem validação.

Fluxo recomendado:

```text
Origem
  ↓
Validar acesso ao destino
  ↓
Copiar arquivo
  ↓
Validar tamanho
  ↓
Validar hash
  ↓
Registrar sucesso
  ↓
Remover origem
```

Em discos diferentes, uma operação de `move` normalmente equivale a copiar e apagar. Portanto, a validação deve ocorrer antes da remoção do arquivo original.

Regras importantes:

- Nunca sobrescrever silenciosamente.
- Resolver conflitos de nomes.
- Registrar cada operação.
- Permitir retomada após interrupção.
- Usar transações no banco.
- Manter um modo de simulação.
- Não apagar o arquivo original quando a validação falhar.

---

## 16. Relatório final

O sistema deve produzir um relatório em HTML e, opcionalmente, JSON ou CSV.

Conteúdo sugerido:

- Total de arquivos encontrados.
- Total analisado.
- Total movido.
- Total ignorado.
- Total com erros.
- Total por categoria.
- Total por tema.
- Total por país.
- Duplicatas encontradas.
- Arquivos sem metadados.
- Arquivos que exigem revisão.
- Erros de leitura.
- Erros de classificação.
- Erros de cópia.
- Erros de validação.
- Caminho de origem e destino de cada operação.

---

## 17. Fases de implementação

### Fase 1 — Inventário

- Seleção de diretório.
- Leitura recursiva.
- Identificação de MIME.
- Extração de metadados.
- Geração de hash.
- Persistência no SQLite.

### Fase 2 — Classificação técnica

- Vídeo.
- Screenshot.
- WhatsApp.
- iPhone.
- RAW.
- Outros.
- Nível de confiança.

### Fase 3 — Interface local

- FastAPI.
- Next.js.
- Progresso do processamento.
- Visualização e filtros.
- Revisão manual.

### Fase 4 — Tema principal

- SigLIP 2.
- Lista inicial de categorias.
- Armazenamento de scores.
- Calibração de confiança.

### Fase 5 — Análise avançada

- Qwen3-VL para casos ambíguos.
- Florence-2 para OCR e legendas.
- Saída estruturada.
- Revisão das categorias.

### Fase 6 — Movimentação

- Mapeamento de destinos.
- Modo de simulação.
- Confirmação.
- Cópia e hash.
- Remoção segura da origem.
- Relatório final.

### Fase 7 — Biblioteca inteligente

- Embeddings.
- FAISS.
- Busca por texto.
- Clustering.
- Álbuns automáticos.
- Detecção de duplicatas visuais.
- Processamento de vídeos.

---

## 18. Ordem recomendada para o MVP

A primeira versão deve priorizar segurança e rastreabilidade:

1. Leitura dos arquivos.
2. Extração de metadados.
3. Classificação por regras.
4. Banco de dados.
5. Interface de revisão.
6. Modo de simulação da movimentação.
7. Movimentação validada.
8. SigLIP 2.
9. Qwen3-VL somente para exceções.
10. Busca semântica e agrupamento.

A inteligência artificial não deve ser o primeiro componente do sistema. Antes dela, o pipeline de inventário, persistência, revisão e movimentação segura precisa estar confiável.

---

## 19. Modelos escolhidos para o MVP

Seleção inicial:

```text
google/siglip2-so400m-patch14-384
Qwen/Qwen3-VL-4B-Instruct
microsoft/Florence-2-large
```

Responsabilidades:

| Componente | Responsabilidade |
|---|---|
| Regras e EXIF | Origem, dispositivo, formato, localização e tipo técnico |
| SigLIP 2 | Tema principal e embeddings |
| Qwen3-VL 4B | Casos ambíguos e análise contextual |
| Florence-2 | OCR, objetos e legendas |
| GeoPandas | Identificação offline do país |
| FFmpeg | Metadados e processamento de vídeo |
| SQLite | Estado do processamento e auditoria |
| FastAPI | API e orquestração |
| Next.js | Interface local |

---

## 20. Princípios do projeto

- Processamento totalmente local.
- Privacidade por padrão.
- Nenhuma movimentação sem confirmação.
- Nenhuma remoção sem validação.
- Toda operação deve ser auditável.
- Classificações devem registrar método e confiança.
- Regras determinísticas devem vir antes da IA.
- Modelos grandes devem ser usados somente quando agregarem valor.
- O sistema deve permitir revisão e correção pelo usuário.
- O pipeline deve ser reiniciável e idempotente.
